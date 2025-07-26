# --- Full End-to-End Contact Finder and Outreach Bot (with Timestamped Reports) ---

import pandas as pd
import re
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Dict, Any
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.message import EmailMessage
from datetime import datetime

# --- 1. SETUP AND INITIALIZATION ---
load_dotenv()

try:
    from langchain_community.tools.tavily_search import TavilySearchResults

    web_search_tool = TavilySearchResults(max_results=3)
    print("✅ Tavily search tool initialized.")
except Exception as e:
    print(f"❌ FAILED to initialize Tavily: {e}. Exiting.")
    exit()


# --- 2. STATE DEFINITION ---
class GraphState(TypedDict):
    people_to_process: List[Dict[str, Any]]
    current_person: Dict[str, Any]
    current_person_contacts: Dict[str, Any]
    social_platforms_to_search: List[str]
    completed_people: List[Dict[str, Any]]
    emails_sent_log: List[Dict[str, Any]]
    api_calls_made: int
    api_call_limit: int


# --- 3. GRAPH NODE DEFINITIONS ---
graph_builder = StateGraph(GraphState)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b")
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}")


def start_processing(state: GraphState) -> GraphState:
    print("--- Reading Excel and Initializing Workflow ---")
    df = pd.read_excel("data.xlsx")
    state['people_to_process'] = df.to_dict(orient="records")
    state['completed_people'] = []
    state['emails_sent_log'] = []
    state['api_calls_made'] = 0
    try:
        state['api_call_limit'] = int(os.getenv("MAX_API_CALLS", 100))
        print(f"✅ API Call Limit set to: {state['api_call_limit']}")
    except (ValueError, TypeError):
        state['api_call_limit'] = 100
        print(f"⚠️ MAX_API_CALLS in .env is not a valid number. Defaulting to {state['api_call_limit']}.")
    return state


def get_next_person(state: GraphState) -> GraphState:
    if not state['people_to_process']:
        return state
    person = state['people_to_process'].pop(0)
    print(f"\n{'=' * 50}\n--- Processing Person: {person['NAME']} ---\n{'=' * 50}")
    state['current_person'] = person
    state['current_person_contacts'] = {"emails": set(), "phones": set(), "sources": {}}
    state['social_platforms_to_search'] = ["LinkedIn", "Facebook", "Twitter", "Instagram"]
    return state


def find_and_scrape_website(state: GraphState) -> GraphState:
    person = state['current_person']
    print(f"  -> Phase 1: Searching for official website for {person['NAME']}")
    query = f"{person.get('NAME')} {person.get('CITY', '')} official website"
    try:
        state['api_calls_made'] += 1
        print(f"    (API Call #{state['api_calls_made']})")
        search_results = web_search_tool.invoke(query)
        if not search_results:
            print("    - No website found in search results.")
            return state
        url_to_scrape = search_results[0]['url']
        print(f"    - Found potential website: {url_to_scrape}. Now scraping.")
        response = requests.get(url_to_scrape, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        emails = set(EMAIL_RE.findall(text))
        phones = set(PHONE_RE.findall(text))
        if emails or phones:
            print(f"    ✅ Found {len(emails)} emails, {len(phones)} phones on website.")
            state['current_person_contacts']['emails'].update(emails)
            state['current_person_contacts']['phones'].update(phones)
            for email in emails: state['current_person_contacts']['sources'][email] = "Official Website"
            for phone in phones: state['current_person_contacts']['sources'][phone] = "Official Website"
    except Exception as e:
        print(f"    ❌ An error occurred during website scraping: {e}")
    return state


def search_next_social_platform(state: GraphState) -> GraphState:
    platform = state['social_platforms_to_search'].pop(0)
    person = state['current_person']
    print(f"  -> Phase 2: Searching {platform} for {person['NAME']}")
    query = f"{person.get('NAME')} {person.get('CITY', '')} {platform} contact"
    try:
        state['api_calls_made'] += 1
        print(f"    (API Call #{state['api_calls_made']})")
        resp = web_search_tool.invoke(query)
        text = str(resp)
        emails = set(EMAIL_RE.findall(text))
        phones = set(PHONE_RE.findall(text))
        if emails or phones:
            print(f"    ✅ Found {len(emails)} emails, {len(phones)} phones via {platform} search.")
            state['current_person_contacts']['emails'].update(emails)
            state['current_person_contacts']['phones'].update(phones)
            for email in emails:
                if email not in state['current_person_contacts']['sources']:
                    state['current_person_contacts']['sources'][email] = platform
            for phone in phones:
                if phone not in state['current_person_contacts']['sources']:
                    state['current_person_contacts']['sources'][phone] = platform
    except Exception as e:
        print(f"    ❌ An error occurred during {platform} search: {e}")
    return state


def send_email(state: GraphState) -> GraphState:
    print("  -> Phase 3: Sending Email...")
    contacts = state['current_person_contacts']
    person = state['current_person']
    if not contacts['emails']:
        print("    - No email address found. Skipping email.")
        return state
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    if not sender_email or not sender_password:
        print("    ❌ Email credentials not found in .env file. Skipping email.")
        return state
    recipient_email = list(contacts['emails'])[0]
    recipient_name = person.get("NAME", "there")
    msg = EmailMessage()
    msg['Subject'] = f"A quick question, {recipient_name}"
    msg['From'] = sender_email
    msg['To'] = recipient_email
    body = f"Hi {recipient_name},\n\nI hope this message finds you well.\n\nI found your contact information online and wanted to reach out regarding a potential collaboration.\n\nBest regards,\n[Your Name]"
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            print(f"    ✅ Email sent successfully to {recipient_name} at {recipient_email}")
            state['emails_sent_log'].append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Name": recipient_name,
                "Email Sent To": recipient_email,
                "Source of Email": contacts['sources'].get(recipient_email, "Unknown")
            })
    except Exception as e:
        print(f"    ❌ Failed to send email to {recipient_email}: {e}")
    return state


def save_and_loop(state: GraphState) -> GraphState:
    person = state['current_person']
    contacts = state['current_person_contacts']
    person['Emails'] = ", ".join(sorted(contacts['emails']))
    person['Phones'] = ", ".join(sorted(contacts['phones']))
    source_list = [f"{item} ({source})" for item, source in contacts['sources'].items()]
    person['Contact Sources'] = "; ".join(sorted(source_list))
    state['completed_people'].append(person)
    print(f"--- Finished processing {person['NAME']}. Data saved. ---")
    return state


# <<< THIS IS THE ONLY NODE THAT HAS BEEN MODIFIED >>>
def generate_final_report(state: GraphState) -> GraphState:
    """Writes all collected data to timestamped Excel files in a 'reports' folder."""
    print(f"\n{'=' * 50}\n--- All People Processed. Generating Final Reports. ---\n{'=' * 50}")
    print(f"Total API Calls Made: {state['api_calls_made']} (Limit was {state['api_call_limit']})")

    # --- Start of New Logic ---
    # 1. Define the output folder and create a consistent timestamp for this run
    output_folder = "reports"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")  # Filename-safe format

    # 2. Ensure the output folder exists. Create it if it doesn't.
    os.makedirs(output_folder, exist_ok=True)
    print(f"Reports will be saved in the '{output_folder}/' directory.")
    # --- End of New Logic ---

    if not state['completed_people']:
        print("⚠️ No data was processed to generate a report.")
        return state

    # 3. Main Output File with new timestamped path
    main_report_filename = f"output_with_contacts_{timestamp}.xlsx"
    main_report_filepath = os.path.join(output_folder, main_report_filename)
    pd.DataFrame(state['completed_people']).to_excel(main_report_filepath, index=False)
    print(f"✅ Main export complete: {main_report_filepath}")

    # 4. Email Sent Log with new timestamped path
    if state['emails_sent_log']:
        email_log_filename = f"emails_sent_log_{timestamp}.xlsx"
        email_log_filepath = os.path.join(output_folder, email_log_filename)
        pd.DataFrame(state['emails_sent_log']).to_excel(email_log_filepath, index=False)
        print(f"✅ Email log complete: {email_log_filepath}")

    # 5. Effectiveness Report with new timestamped path
    platform_counts = {}
    for person in state['completed_people']:
        sources_str = person.get('Contact Sources', '')
        sources_list = re.findall(r'\((.*?)\)', sources_str)
        for source in sources_list:
            platform_counts[source] = platform_counts.get(source, 0) + 1
    if platform_counts:
        effectiveness_filename = f"platform_effectiveness_report_{timestamp}.xlsx"
        effectiveness_filepath = os.path.join(output_folder, effectiveness_filename)
        report_df = pd.DataFrame(list(platform_counts.items()), columns=['Platform', 'Contacts Found'])
        report_df = report_df.sort_values(by="Contacts Found", ascending=False)
        report_df.to_excel(effectiveness_filepath, index=False)
        print(f"✅ Effectiveness report complete: {effectiveness_filepath}")

    print("--- Workflow Finished ---")
    return state


# --- 4. CONDITIONAL LOGIC FUNCTIONS ---
def check_api_limit_before_processing(state: GraphState) -> str:
    if state['api_calls_made'] >= state['api_call_limit']:
        print("\n🚨 API CALL LIMIT REACHED! Halting all further processing.")
        return "limit_reached"
    else:
        return "can_proceed"


def should_continue_to_social(state: GraphState) -> str:
    contacts = state['current_person_contacts']
    if contacts['emails'] and contacts['phones']:
        print("  ✅ Goal met on website. Proceeding to send email.")
        return "send_email"
    else:
        print("  - Goal not met. Continuing to social media.")
        return "search_social"


def should_continue_social_search(state: GraphState) -> str:
    contacts = state['current_person_contacts']
    if contacts['emails'] and contacts['phones']:
        print("  ✅ Goal met on social media. Proceeding to send email.")
        return "send_email"
    if state['api_calls_made'] >= state['api_call_limit']:
        print("\n🚨 API CALL LIMIT REACHED! Halting further social searches for this person.")
        return "save_and_loop"
    if not state['social_platforms_to_search']:
        print("  - No more social platforms to search for this person.")
        return "save_and_loop"
    return "continue_social_search"


def should_continue_processing(state: GraphState) -> str:
    if state['people_to_process']:
        return "get_next_person"
    else:
        return "generate_final_report"


# --- 5. BUILD THE GRAPH ---
graph_builder.add_node("start_processing", start_processing)
graph_builder.add_node("get_next_person", get_next_person)
graph_builder.add_node("find_and_scrape_website", find_and_scrape_website)
graph_builder.add_node("search_next_social_platform", search_next_social_platform)
graph_builder.add_node("send_email", send_email)
graph_builder.add_node("save_and_loop", save_and_loop)
graph_builder.add_node("generate_final_report", generate_final_report)

graph_builder.add_edge(START, "start_processing")
graph_builder.add_edge("start_processing", "get_next_person")

graph_builder.add_conditional_edges(
    "get_next_person",
    check_api_limit_before_processing,
    {"can_proceed": "find_and_scrape_website", "limit_reached": "generate_final_report"}
)

graph_builder.add_conditional_edges(
    "find_and_scrape_website",
    should_continue_to_social,
    {"send_email": "send_email", "search_social": "search_next_social_platform", "save_and_loop": "save_and_loop"}
)

graph_builder.add_conditional_edges(
    "search_next_social_platform",
    should_continue_social_search,
    {"send_email": "send_email", "continue_social_search": "search_next_social_platform",
     "save_and_loop": "save_and_loop"}
)

graph_builder.add_edge("send_email", "save_and_loop")

graph_builder.add_conditional_edges(
    "save_and_loop",
    should_continue_processing,
    {"get_next_person": "get_next_person", "generate_final_report": "generate_final_report"}
)

graph_builder.add_edge("generate_final_report", END)

# --- 6. COMPILE AND RUN ---
if __name__ == "__main__":
    app = graph_builder.compile()
    app.invoke({})