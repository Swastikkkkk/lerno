# Lerno.ai - Revolutionizing ed-tech with AI-Driven Personalization

## Overview

An AI-powered learning platform that visualizes concepts to enhance student understanding and retention. Lerno.ai is an intelligent learning platform that combines frontend web technologies with backend services in Node.js and FastAPI to deliver a comprehensive educational experience.

Check out the PPT for details! - https://www.figma.com/slides/2P1pYfOLMtQcbQfyhlG9fi/lerno.ai-CTRL-ALT-DEFEAT?node-id=0-239&t=EhwKERTP5aHifi0N-1

## Project Setup

### Prerequisites

- Node.js (v14 or higher)
- Python (v3.8 or higher)
- npm or yarn

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/suryansh04/Lerno.ai-HackoWasp-7.0--Ctrl-Alt-Defeat
cd Lerno.ai-HackoWasp-7.0--Ctrl-Alt-Defeat
```

### 2. Frontend Setup

Install the required dependencies:

```bash
npm install
```

### 3. Backend Setup Node.js Backend

Navigate to the backend directory and install dependencies:

```bash
cd backend
npm install
```

Python FastAPI Backend
Install the required Python packages:

```bash
cd backend
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a .env file in the root directory with the following variables:

```plaintext
# API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key
GEMINI_API_KEY=your_gemini_api_key
```

## Running the Application

### 1. Start the Frontend Development Server

From the root directory:

```bash
npm run dev
```

### 2. Start the Node.js Backend Server

In a new terminal, navigate to the backend directory:

```bash
cd backend
node server.js
```

### 3. Start the FastAPI Server

In another terminal, navigate to the backend directory:

```bash
cd backend
uvicorn main:app
```

## Project Structure

```plaintext
lerno-ai/
├── public/
├── src/
│   ├── components/
│   ├── pages/
│   ├── styles/
│   └── App.js
├── backend/
│   ├── node/
│   │   └── server.js
│   ├── python/
│   │   ├── main.py
│   │   └── requirements.txt
│   └── requirements.txt
├── .env
├── package.json
└── README.md
```

## Troubleshooting

### Common Issues

1. API Key Issues : Ensure all API keys in the .env file are correct and have the necessary permissions.
2. Port Conflicts : If you encounter port conflicts, modify the PORT variables in the .env file.
3. Dependency Issues : Make sure all dependencies are installed correctly with npm install and pip install -r requirements.txt .
