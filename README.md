# 🤖 Contact Finder AI Agent

An intelligent, rule-based agent that automates contact discovery and outreach. This tool efficiently finds emails and phone numbers from official websites and social media, with built-in cost controls and automated email capabilities.

![Contact Finder Agent Demo](https://github.com/user-attachments/assets/242b752b-7efa-46dd-94b9-204f937f9918) <!-- It's highly recommended to add a GIF of your script running here -->

## ✨ Key Features

- **Intelligent Search Strategy:** Prioritizes scraping official websites before moving to social media to get the most accurate data first.
- **Efficient & Cost-Effective:** Automatically halts searching for a person as soon as the goal (email + phone) is met, reducing redundant API calls.
- **API Call Limiter:** Set a hard cap on API searches in the `.env` file to prevent unexpected costs.
- **Automated Email Outreach:** Can send personalized introductory emails via Gmail upon successful contact discovery.
- **Comprehensive Reporting:** Generates three timestamped reports in a `/reports` folder for each run:
  1. `output_with_contacts_[timestamp].xlsx`: The master list of all contacts found.
  2. `emails_sent_log_[timestamp].xlsx`: A log of every email sent by the agent.
  3. `platform_effectiveness_report_[timestamp].xlsx`: An analysis of which platforms yielded the most contacts.

## 🛠️ Setup & Installation

Follow these steps to get the agent running on your local machine.

### 1. Prerequisites

- Python 3.8 or newer
- A free API key from [Tavily AI](https://tavily.com/)
- A Gmail account with 2-Factor Authentication enabled

### 2. Clone the Repository

Open your terminal and run:
```bash
git clone https://github.com/Saadkhanhere/contact-finder-agent.git
cd contact-finder-agent# contact-finder-agent
