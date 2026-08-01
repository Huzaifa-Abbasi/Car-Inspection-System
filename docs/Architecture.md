# System Architecture

The Car Inspection System is built as a desktop-native web application combining a Python backend and a lightweight HTML5/JS frontend.

## Components

### 1. Frontend
* **UI Structure**: Vanilla HTML5, styled with modern CSS variables.
* **Logic (`frontend/js/`)**:
  * `app.js`: Main router and layout coordinator.
  * `detection.js`: Manages WebSocket connections for live feeds and dynamically transmits adjust sliders.
  * `history.js`: Renders inspection records and enforces client-side [[User Roles]].
* **Visual Annotations**: Powered by `agentation-vanilla` for live design feedback.

### 2. Backend
* **API Framework**: FastAPI, serving static files and REST routes.
* **Database**: SQLite managed through SQLAlchemy ORM.
* **Live Streaming**: WebSocket routes (`backend/routes/ws_routes.py`) that stream processed frames as base64-encoded JPEG chunks.
* **Process Flow**: Wires up camera inputs to the **[[Detection Pipeline]]**.

## System Diagrams

For draw.io diagrams and report graphics, see [docs/diagrams/README.md](file:///d:/Personal%20Projects/Car%20Inspection/docs/diagrams/README.md):
- [1_System_Architecture.mmd](file:///d:/Personal%20Projects/Car%20Inspection/docs/diagrams/1_System_Architecture.mmd)
- [2_AI_Detection_Pipeline.mmd](file:///d:/Personal%20Projects/Car%20Inspection/docs/diagrams/2_AI_Detection_Pipeline.mmd)
- [3_Inspection_Workflow_Sequence.mmd](file:///d:/Personal%20Projects/Car%20Inspection/docs/diagrams/3_Inspection_Workflow_Sequence.mmd)
- [4_Database_ERD.mmd](file:///d:/Personal%20Projects/Car%20Inspection/docs/diagrams/4_Database_ERD.mmd)
- [5_User_Roles_RBAC_Security.mmd](file:///d:/Personal%20Projects/Car%20Inspection/docs/diagrams/5_User_Roles_RBAC_Security.mmd)
- [6_Inspection_Lifecycle_State_Machine.mmd](file:///d:/Personal%20Projects/Car%20Inspection/docs/diagrams/6_Inspection_Lifecycle_State_Machine.mmd)

