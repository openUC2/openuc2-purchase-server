# Purchase Ledger

A local web application for recording purchases, tracking product price histories, managing deliveries, and exporting data. All data is stored locally in a JSON file.

---

## Project Structure

Ensure your project directory is organized like this before running Docker:

```text
├── Purchase_Ledger.py    # Flask backend server
├── index.html            # Frontend single-page application[cite: 1]
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container build instructions
├── docker-compose.yml    # Docker Compose orchestration
└── data/                 # Created automatically to store ledger.json & backups[cite: 2]