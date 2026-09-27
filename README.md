# 🚗 AutoScan Pro — Vehicle Inspection System

Welcome to **AutoScan Pro**, an AI-powered desktop vehicle inspection system. This software automatically detects car defects (scratches, dents, structural damage) using AI computer vision models and generates detailed PDF inspection reports.

This guide is written specifically for **non-technical users**. Follow the simple step-by-step instructions below to install, set up, and run the program on your computer.

---

## 📋 Table of Contents
1. [System Requirements](#-system-requirements)
2. [Step 1: Install Python](#-step-1-install-python-critical)
3. [Step 2: Download the Project](#-step-2-download-the-project)
4. [Step 3: Open Terminal / Command Prompt](#-step-3-open-terminal--command-prompt)
5. [Step 4: Create & Activate Virtual Environment](#-step-4-create--activate-virtual-environment)
6. [Step 5: Install Dependencies](#-step-5-install-dependencies)
7. [Step 6: Setup Configuration (.env)](#-step-6-setup-configuration-env)
8. [🚀 How to Run the Application](#-how-to-run-the-application)
9. [🖥️ Creating a Standalone Windows App (.exe)](#%EF%B8%8F-creating-a-standalone-windows-app-exe)
10. [📖 User Guide (How to Use)](#-user-guide-how-to-use)
11. [❓ Troubleshooting & Common Errors](#-troubleshooting--common-errors)

---

## 💻 System Requirements

| Requirement | Recommended Specs |
| :--- | :--- |
| **Operating System** | Windows 10 or Windows 11 (64-bit) |
| **Python Version** | **Python 3.10.x** or **Python 3.11.x** (Required) |
| **RAM** | 8 GB or higher |
| **Camera** | Built-in Webcam or USB HD Web Camera (For live video scanning) |
| **Storage** | 2 GB free disk space |

---

## 📥 Step 1: Install Python (CRITICAL)

Before running the application, Python must be installed on your system.

1. Download **Python 3.11** from the official site:
   👉 [https://www.python.org/downloads/release/python-3118/](https://www.python.org/downloads/release/python-3118/)
2. Run the downloaded installer.
3. ⚠️ **VERY IMPORTANT STEP**: On the first installer screen, check the box that says:
   `✅ Add python.exe to PATH` (at the bottom of the window).
4. Click **Install Now**.
5. Once installation finishes, close the installer.

---

## 📥 Step 2: Download the Project

If you received this code as a `.zip` file or Git repository:

- **If downloaded as ZIP**: Extract/Unzip the folder to your computer (e.g., `D:\Personal Projects\Car Inspection` or `C:\Car Inspection`).
- **If using Git**: Run this command in your terminal:
  ```powershell
  git clone https://github.com/Huzaifa-Abbasi/Car-Inspection-System.git
  ```

---

## 💻 Step 3: Open Terminal / Command Prompt

1. Open the project folder in File Explorer (`Car Inspection`).
2. Click on the address bar at the top of File Explorer.
3. Type `cmd` or `powershell` and press **Enter**.
4. A black terminal window will open, positioned directly inside your project folder.

---

## ⚙️ Step 4: Create & Activate Virtual Environment

A virtual environment isolates project dependencies so they don't interfere with other Python programs.

Run the following commands one by one in your terminal:

### Command 1: Create the Virtual Environment
```powershell
python -m venv .venv
```
*(Wait 10-15 seconds for it to finish)*

### Command 2: Activate the Virtual Environment
- **On Windows (Command Prompt / PowerShell)**:
  ```powershell
  .venv\Scripts\activate
  ```
- **On macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

👉 **How to check if it worked**: You will see `(.venv)` in green or brackets at the start of your command prompt line:
```text
(.venv) PS D:\Personal Projects\Car Inspection>
```

---

## 📦 Step 5: Install Dependencies

Now install all necessary libraries required by the AI model, backend server, desktop interface, and PDF generator.

### Command 1: Upgrade Package Installer (pip)
```powershell
python -m pip install --upgrade pip
```

### Command 2: Install All Required Packages
```powershell
pip install -r requirements.txt
```
*(This will download and install OpenCV, PyWebView, FastAPI, Ultralytics YOLOv8, SQLAlchemy, WeasyPrint, etc. It may take 2–5 minutes depending on your internet speed).*

---

## ⚙️ Step 6: Setup Configuration (.env)

The project uses a configuration file named `.env` for database settings and passwords.

1. In the main project folder, check if a file named `.env` exists.
2. If not, create a file named `.env` using Notepad and add the following lines:

```ini
# Car Inspection Configuration
DATABASE_URL=sqlite:///./data/car_inspection.db
JWT_SECRET=autoscan-pro-secret-key-change-this-12345
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=480

# SMTP Email Configuration (Optional - for emailing PDF reports)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Company Info
COMPANY_NAME=AutoScan Pro
COMPANY_TAGLINE=Professional Vehicle Inspection System

# Server Host & Port
HOST=127.0.0.1
PORT=8000
```
*(Save and close the file).*

---

## 🚀 How to Run the Application

You have 2 ways to run the application depending on your use case:

### Option A: Launch Full Desktop Application (RECOMMENDED)

This starts the backend API and opens a native window containing the full dashboard, inspection manager, camera feed, and PDF export tool.

Make sure your virtual environment is active `(.venv)` and run:

```powershell
python main.py
```

- A window titled **"AutoScan Pro — Vehicle Inspection System"** will pop up automatically.
- If PyWebView is not supported on your system, it will open automatically in your web browser at `http://127.0.0.1:8000`.

---

### Option B: Quick Live Camera Inspection Feed

If you only want to test the camera feed and AI defect detection model directly in an OpenCV window:

```powershell
python app.py
```

- Press **`q`** on your keyboard while the window is focused to exit the camera feed.

---

## 🖥️ Creating a Standalone Windows App (.exe)

You can package the entire application into a single executable folder so non-technical users can run it by simply double-clicking an `.exe` file without installing Python or opening terminal.

Run the build script:

```powershell
python build_project.py
```

1. The script will automatically install PyInstaller, bundle the AI model (`best.pt`, `yolov8n.pt`), frontend templates, and libraries.
2. Once complete, find your app inside:
   ```text
   dist\AutoScanPro\AutoScanPro.exe
   ```
3. Double-click `AutoScanPro.exe` to launch!

---

## 📖 User Guide (How to Use)

1. **Dashboard & Login**:
   - Log in using your registered credentials.
   - View overview metrics: Total Inspections, Total Defects Found, Completed Reports.
2. **Start Inspection**:
   - Enter Vehicle Info: Make, Model, License Plate Number, VIN, Customer Name.
   - Select Inspection Type: Routine, Pre-Purchase, Post-Accident.
3. **AI Defect Detection**:
   - Point your camera at the vehicle or upload vehicle images.
   - The AI automatically highlights defects (dents, scratches, cracks) with bounding boxes and confidence percentages.
4. **Generate PDF Report**:
   - Click **Save Report PDF**.
   - A file dialog will prompt you to choose where to save your PDF report.
   - The PDF includes full vehicle details, defect breakdown table, inspector notes, and company header.

---

## ❓ Troubleshooting & Common Errors

### ❌ 1. 'python' is not recognized as an internal or external command
- **Cause**: Python was installed without checking the "Add to PATH" box.
- **Fix**: Re-run the Python installer, choose **Modify**, and check `Add Python to PATH`.

### ❌ 2. Camera feed is black or shows error
- **Cause**: Another app (Zoom, Teams, Skype) is using your webcam, or webcam permissions are blocked.
- **Fix**: Close all other apps using the camera. In Windows Settings, go to **Privacy & Security > Camera** and allow apps to access your camera.

### ❌ 3. Port 8000 is already in use
- **Cause**: Another program or a background AutoScan instance is using port 8000.
- **Fix**: Open `.env` and change `PORT=8000` to `PORT=8080`.

### ❌ 4. PyWebView fail / window doesn't open
- **Cause**: Missing Webview component or GUI display server.
- **Fix**: AutoScan Pro automatically falls back to your browser (`http://127.0.0.1:8000`). Just open that address in Chrome, Edge, or Firefox.

### ❌ 5. PDF generation error (WeasyPrint / GTK / Cairo)
- **Cause**: WeasyPrint requires Cairo GTK library on Windows.
- **Fix**: AutoScan Pro has fallback engines (`xhtml2pdf` and `ReportLab`). If you see a PDF rendering warning, install GTK for Windows or let AutoScan Pro automatically fall back to ReportLab.

---

## 📁 Project Structure

```text
Car Inspection/
├── backend/                  # FastAPI Backend API & Database Models
│   ├── app.py                # Server App Factory
│   ├── database.py           # SQLite Database Connection
│   ├── models.py             # Database Tables (Vehicles, Inspections, Defects)
│   ├── routes/               # API Routes (Auth, Vehicles, Inspections, Reports)
│   ├── services/             # Report Generation & Logic
│   └── templates/            # HTML PDF Report Templates
├── frontend/                 # Web Interface (HTML, CSS, JS)
├── src/                      # AI Vision Pipeline & OpenCV Tracking
│   ├── detector.py           # YOLOv8 Object Detector
│   └── pipeline.py           # Video Frame Processing & Stabilization
├── data/                     # Local SQLite Database Files
├── best.pt                   # Trained YOLO Defect Detection Weights
├── yolov8n.pt                # Base YOLO Model Weights
├── main.py                   # Desktop Entry Point (PyWebView + Server)
├── app.py                    # OpenCV Live Camera Feed Script
├── build_project.py          # PyInstaller Executable Builder
├── requirements.txt          # Required Python Libraries list
├── .env                      # Configuration Settings
└── README.md                 # This user guide
```

---

## 💡 Quick Reference Sheet

| Action | Command |
| :--- | :--- |
| **Activate Virtual Environment** | `.venv\Scripts\activate` |
| **Install Requirements** | `pip install -r requirements.txt` |
| **Run Desktop App** | `python main.py` |
| **Run Live Camera Feed** | `python app.py` |
| **Build Executable (.exe)** | `python build_project.py` |

---

*AutoScan Pro — Built with Python, FastAPI, PyWebView, OpenCV & YOLOv8.*
