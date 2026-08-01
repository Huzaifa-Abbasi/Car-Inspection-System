# System Architecture & Final Report Diagrams (draw.io / Mermaid)

This directory contains the essential software engineering, AI pipeline, database, and security diagrams created for the **AutoScan Pro Vehicle Inspection System** final report.

Each diagram is provided in clean Mermaid.js format, fully compatible with **draw.io** (diagrams.net), GitHub Markdown, and VS Code previews.

---

## Index of Diagrams

1. [System Architecture Diagram](#1-system-architecture-diagram) (`1_System_Architecture.mmd`)
2. [AI Computer Vision & Detection Pipeline](#2-ai-computer-vision--detection-pipeline) (`2_AI_Detection_Pipeline.mmd`)
3. [End-to-End Inspection Sequence Diagram](#3-end-to-end-inspection-sequence-diagram) (`3_Inspection_Workflow_Sequence.mmd`)
4. [Entity-Relationship Diagram (Database Schema)](#4-entity-relationship-diagram-database-schema) (`4_Database_ERD.mmd`)
5. [User Roles & Security Access Control (RBAC)](#5-user-roles--security-access-control-rbac) (`5_User_Roles_RBAC_Security.mmd`)
6. [Inspection Lifecycle State Machine](#6-inspection-lifecycle-state-machine) (`6_Inspection_Lifecycle_State_Machine.mmd`)

---

## 1. System Architecture Diagram

Represents the multi-tier desktop architecture: PyWebView Frontend, FastAPI Backend, OpenCV/YOLO Detection Engine, and SQLite Persistence Layer.

```mermaid
flowchart TB
    subgraph ClientLayer ["Client Layer (Desktop App)"]
        WV["PyWebView Desktop Window"]
        HTML["HTML5 / CSS3 Interface"]
        subgraph JSModules ["JS Logic Modules"]
            APP["app.js (Router & Layout)"]
            AUTH_JS["auth.js (RBAC & JWT)"]
            DET_JS["detection.js (WS Stream)"]
            HIST_JS["history.js (Data Table)"]
        end
    end

    subgraph BackendLayer ["Backend Layer (FastAPI & Python)"]
        UVI["Uvicorn Server (Port 8000)"]
        FASTAPI["FastAPI Application"]
        
        subgraph APIRoutes ["API & WebSockets"]
            AUTH_R["Auth Routes (/api/auth)"]
            VEH_R["Vehicle Routes (/api/vehicles)"]
            INSP_R["Inspection Routes (/api/inspections)"]
            DEF_R["Defect Routes (/api/defects)"]
            REP_R["Report Routes (/api/reports)"]
            WS_R["WebSocket Stream (/ws/inspect)"]
        end

        JWT["JWT Security & RBAC Middleware"]
    end

    subgraph CVPipeline ["AI / Computer Vision Engine"]
        GATE["Stage 1: YOLOv8n Gate (Vehicle Check)"]
        CROP["Stage 2: 640w Resizer & ROI Cropper"]
        MODEL["Stage 3: YOLOv8 Specialist (best.pt)"]
        OPENCV["Stage 4: OpenCV Geometry & Stability Filter"]
    end

    subgraph PersistenceLayer ["Persistence & Storage"]
        DB[(SQLite Database)]
        ORMS["SQLAlchemy ORM Models"]
        FILES["Snapshot Images & PDF Reports"]
    end

    WV --> HTML
    HTML --> JSModules
    JSModules -- HTTP / JSON --> APIRoutes
    DET_JS -- WebSocket --> WS_R
    APIRoutes --> JWT
    JWT --> ORMS
    WS_R <--> CVPipeline
    CVPipeline --> FILES
    ORMS --> DB
    REP_R --> FILES
```

---

## 2. AI Computer Vision & Detection Pipeline

Illustrates the two-stage cascaded inference flow: YOLOv8n Vehicle Gate, 640w ROI Alignment, Custom Specialist (`best.pt`), Confidence/NMS filtering, OpenCV Contour Geometry Analysis, and the 5-Frame Temporal Stability Filter.

```mermaid
flowchart TD
    Start([Camera Feed / Video Frame Input]) --> Stage1{Stage 1: Vehicle Gate<br/>YOLOv8n Pre-trained}
    
    Stage1 -- "No Vehicle Detected" --> GateCheck{Require Vehicle<br/>Gate Active?}
    GateCheck -- "Yes" --> CleanOutput[Discard / Suppress Frame<br/>Zero Defect Output]
    GateCheck -- "No" --> Stage2
    
    Stage1 -- "Vehicle Present (Car/Bus/Truck)" --> Stage2[Stage 2: ROI Cropping & Alignment<br/>Resize ROI to 640x640]
    
    Stage2 --> Stage3[Stage 3: Fault Specialist Model<br/>YOLOv8 best.pt - 15 Classes]
    
    Stage3 --> FilterConf{Confidence >= 0.35?}
    FilterConf -- "No" --> RejectLow[Drop Low-Confidence Bounding Box]
    FilterConf -- "Yes" --> NMS[Apply NMS IoU Overlap<br/>IoU Threshold = 0.30]
    
    NMS --> Stage4[Stage 4: OpenCV Contour Analysis<br/>Shape Geometry Classification]
    
    Stage4 --> Stability{5-Frame Stability Filter<br/>Bounding Box Persists?}
    Stability -- "No (Flicker)" --> Suppress[Suppress Live Artifact]
    Stability -- "Yes (Stable)" --> FinalDefect[Confirmed Defect Record]
    
    FinalDefect --> LogDB[(Save Defect to DB<br/>with BBox Coordinates)]
    FinalDefect --> SaveSnap[Crop & Save Defect Snapshot PNG]
    FinalDefect --> WSBroadcast[WebSocket Base64 Stream<br/>Draw Canvas Overlay in UI]
```

---

## 3. End-to-End Inspection Sequence Diagram

Details the step-by-step communication between Inspector, Frontend UI, Authentication, Inspection API, WebSocket Live Stream, Computer Vision Engine, Database, and WeasyPrint PDF Generation Engine.

```mermaid
sequenceDiagram
    autonumber
    actor Inspector as Inspector / User
    participant UI as Frontend App
    participant Auth as Auth Controller
    participant Insp as Inspection API
    participant WS as WebSocket Server
    participant AI as YOLO / CV Engine
    participant DB as SQLite Database
    participant Rep as Report Engine

    Inspector->>UI: Select Role (Inspector) & Enter Credentials
    UI->>Auth: POST /api/auth/login {email, pass, role}
    Auth->>DB: Query user & verify hash + role
    DB-->>Auth: User record valid
    Auth-->>UI: Return JWT Access Token

    Inspector->>UI: Click "Start New Inspection" & Enter Vehicle Info
    UI->>Insp: POST /api/inspections (Vehicle + Owner Details)
    Insp->>DB: Insert Vehicle & Inspection (status="scanning")
    DB-->>Insp: Inspection ID created
    Insp-->>UI: Return Inspection ID

    UI->>WS: Connect ws://localhost:8000/ws/inspect/{id}
    WS->>AI: Initialize Camera Feed & Detection Pipeline
    
    loop Live Video Frames
        AI->>AI: Run YOLOv8n Gate & YOLOv8 Specialist
        AI-->>WS: Stream Processed Frame (Base64 JPEG + Defects)
        WS-->>UI: Render Annotated Canvas Overlay
    end

    Inspector->>UI: Click "End Scan"
    UI->>WS: Close WebSocket
    UI->>Insp: PATCH /api/inspections/{id}/phase (status="reviewing")
    Insp->>DB: Update Inspection Phase

    Inspector->>UI: Review & Edit Detected Defect List
    Inspector->>UI: Click "Generate Inspection Report"
    UI->>Rep: POST /api/reports/{id}/generate
    Rep->>DB: Fetch Inspection, Vehicle & Defect Snapshots
    Rep->>Rep: Render HTML & Compile PDF via WeasyPrint
    Rep->>DB: Save Report Path & Set status="completed"
    Rep-->>UI: Return HTML & PDF Download URL
    UI-->>Inspector: Display Interactive Report Preview
```

---

## 4. Entity-Relationship Diagram (Database Schema)

Defines relational tables (`users`, `vehicles`, `inspections`, `defects`, `reports`) with primary keys, foreign keys, cardinality, and data types.

```mermaid
erDiagram
    USERS ||--o{ INSPECTIONS : "conducts"
    VEHICLES ||--o{ INSPECTIONS : "belongs to"
    INSPECTIONS ||--|{ DEFECTS : "contains"
    INSPECTIONS ||--o| REPORTS : "generates"

    USERS {
        string id PK "UUID Primary Key"
        string name "Full User Name"
        string email UK "Unique Email Address"
        string password_hash "Bcrypt Password Hash"
        string role "inspector | manager"
        datetime created_at "Registration Timestamp"
    }

    VEHICLES {
        string id PK "UUID Primary Key"
        string make "Vehicle Manufacturer"
        string model "Vehicle Model"
        int year "Manufacturing Year"
        string license_plate "License Plate Number"
        string vin "Vehicle Identification Number"
        string color "Vehicle Paint Color"
        int mileage "Odometer Reading"
        string owner_name "Owner Full Name"
        string owner_email "Owner Contact Email"
        string owner_phone "Owner Phone Number"
        datetime created_at "Creation Timestamp"
    }

    INSPECTIONS {
        string id PK "UUID Primary Key"
        string vehicle_id FK "References VEHICLES(id)"
        string inspector_id FK "References USERS(id)"
        string status "scanning | reviewing | completed"
        string notes "Inspector General Notes"
        datetime started_at "Inspection Start Time"
        datetime completed_at "Inspection End Time"
    }

    DEFECTS {
        string id PK "UUID Primary Key"
        string inspection_id FK "References INSPECTIONS(id)"
        string fault_type "Scratch, Dent, Rust, Crack, etc."
        float confidence "YOLO Detection Confidence (0-1)"
        string severity "low | medium | high | critical"
        string status "detected | confirmed | dismissed"
        int bbox_x1 "Bounding Box Top-Left X"
        int bbox_y1 "Bounding Box Top-Left Y"
        int bbox_x2 "Bounding Box Bottom-Right X"
        int bbox_y2 "Bounding Box Bottom-Right Y"
        string snapshot_path "Path to Cropped Defect Image"
        string notes "Inspector Annotation Notes"
        datetime detected_at "Detection Timestamp"
    }

    REPORTS {
        string id PK "UUID Primary Key"
        string inspection_id FK "References INSPECTIONS(id)"
        string report_path "Path to Generated PDF Report"
        datetime generated_at "Generation Timestamp"
    }
```

---

## 5. User Roles & Security Access Control (RBAC)

Demonstrates security middleware validation, JWT decoding, role verification (`inspector` vs `manager`), and cascaded snapshot file cleanup upon deletion.

```mermaid
flowchart TD
    Start([User Request to API]) --> AuthHeader{Authorization Header<br/>Bearer JWT Token Present?}
    
    AuthHeader -- "Missing / Invalid" --> 401[HTTP 401 Unauthorized<br/>Redirect to Login]
    
    AuthHeader -- "Valid Token" --> Decode[Decode JWT & Extract Claims<br/>user_id & role]
    
    Decode --> CheckRole{User Account Role}
    
    subgraph ManagerScope ["Manager Access Scope"]
        CheckRole -- "manager" --> MgrPerms[Full Administrative Access]
        MgrPerms --> MgrActions["• View ALL User Inspections in History<br/>• Generate & Download Any PDF Report<br/>• Delete ANY Inspection & Defect Log<br/>• Delete Cascade: Remove Snapshot Files from Server"]
    end
    
    subgraph InspectorScope ["Inspector Access Scope"]
        CheckRole -- "inspector" --> InspPerms[Restricted Personal Scope]
        InspPerms --> CheckOwner{Inspection inspector_id<br/>matches Token user_id?}
        CheckOwner -- "Yes" --> InspActions["• View Own Inspections<br/>• Conduct Live Inspections<br/>• Edit Own Defect Reviews<br/>• Delete Own Inspection Logs"]
        CheckOwner -- "No" --> 403[HTTP 403 Forbidden<br/>Access Denied]
    end

    MgrActions --> DBExecute[(Execute SQL & Database Updates)]
    InspActions --> DBExecute
```

---

## 6. Inspection Lifecycle State Machine

Maps out all operational states of a vehicle inspection from application launch to final report generation and history archiving.

```mermaid
stateDiagram-v2
    [*] --> Idle: Application Start

    state "Inspection Lifecycle" as Lifecycle {
        Idle --> Draft: Click "Start New Inspection"
        
        state Draft {
            [*] --> VehicleInput: Fill Make, Model, Year, Plate, VIN
            VehicleInput --> OwnerInput: Fill Owner Contact Info
            OwnerInput --> Confirm: Review Summary & Inspector Notes
        }

        Draft --> Scanning: Click "Start Inspection"

        state Scanning {
            [*] --> WSConnect: Establish WebSocket Stream
            WSConnect --> LiveInference: AI Camera Frame Processing
            LiveInference --> DefectLog: Detect & Log Faults + Snapshots
            DefectLog --> LiveInference: Next Video Frame
        }

        Scanning --> Reviewing: Click "End Scan"

        state Reviewing {
            [*] --> DefectGrid: Render Detected Bounding Boxes
            DefectGrid --> EditDefects: Add/Edit Severity, Status & Notes
            EditDefects --> CleanReportCheck: Clean Report or Defect Report
        }

        Reviewing --> GeneratingReport: Click "Generate Report"

        state GeneratingReport {
            [*] --> CompileHTML: Render HTML Template with Metadata
            CompileHTML --> WeasyPrintPDF: Convert HTML to PDF Document
            WeasyPrintPDF --> SaveReport: Save PDF File to /reports/
        }

        GeneratingReport --> Completed: Report Generation Success

        state Completed {
            [*] --> ViewReport: Display Interactive PDF/HTML Preview
            ViewReport --> HistoryTable: Record Saved in Inspection History
        }
    }

    Completed --> [*]: Inspection Workflow Complete
```

---

## How to Import into draw.io

1. Open **[draw.io (diagrams.net)](https://app.diagrams.net/)**.
2. Click **Arrange > Insert > Advanced > Mermaid...**
3. Paste the Mermaid content of any diagram above into the text box and click **Insert**.
4. You can edit, format, change colors, or export the resulting diagram as XML, PNG, SVG, or PDF for your final project documentation report.
