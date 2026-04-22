# AI Lit Scout

AI-Powered Literature Scout & Summarizer.

## Prerequisites

- Python 3.8+
- Node.js (optional, only if you want to use npm for something, but not strictly required as frontend is static)

## Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

1.  **Start the backend server:**
    Make sure you are in the `backend` directory and your virtual environment is activated.
    ```bash
    uvicorn app:app --reload
    ```
    *Note: The first run may take some time as it downloads necessary ML models.*

2.  **Access the application:**
    Open your web browser and go to:
    [http://localhost:8000](http://localhost:8000)

## Project Structure

-   `backend/`: FastAPI application and ML logic.
-   `frontend/`: Static HTML/CSS/JS files (served by the backend).
-   `results/`: Directory where generated reports and uploads are stored.
