# User Roles & Security

The system enforces **Role-Based Access Control (RBAC)** to protect inspection data and define inspector workflows.

## Defined Roles

### 1. Manager
* **Access Scope**: Full permissions across the entire workspace.
* **Capabilities**:
  * Can view all inspection logs in the history table.
  * Can download PDF reports for any vehicle.
  * Can **delete any inspection record** and its corresponding defect data (which automatically cleans up snapshot files from the backend host).

### 2. Inspector
* **Access Scope**: Restricted to personal inspection logs.
* **Capabilities**:
  * Can only see inspections they created in the history table (filters automatically based on `inspector_id` matching `current_user.id`).
  * Can **only delete their own inspection records**. They do not have access to delete buttons for inspections conducted by other users.

## Enforcement
* **Backend**: Verified on FastAPI route headers using JWT token authentication via `Depends(get_current_user)` inside `backend/routes/inspection_routes.py`.
* **Frontend**: Handled dynamically during rendering inside `history.js` by checking the user metadata saved in local storage.
