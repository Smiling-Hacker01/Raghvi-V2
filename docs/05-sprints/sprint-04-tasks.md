# Sprint 04 — Tasks & Task Management

**Milestone:** M2 (Chat, Memory, Tasks)  
**Sprint Goal:** Users can create, manage, and track tasks. Reminders deferred to M3.

---

## 1. Objective

By the end of this sprint:

- Users can create tasks with title, description, due date
- Users can list tasks (with filters: all, open, completed, overdue)
- Users can mark tasks complete
- Users can edit task details
- Users can delete tasks (soft delete, recoverable later)
- Task due dates are prominently displayed
- Task management is accessible from Android UI
- Raghvi can reference tasks in conversation (optional, nice-to-have for Sprint 04)

---

## 2. Scope

### 2.1 In Scope

**Backend — Database & Models**
- `Task` model: `id`, `user_id`, `title`, `description`, `due_date`, `completed_at`, `created_at`, `updated_at`, `deleted_at`
- Alembic migration for Task table + indexes
- Unique constraint: user_id + title (allow duplicate titles across users, but not within same user)

**Backend — Task Endpoints**
- `POST /tasks` — create task
  - Request: `{"title": "...", "description": "...", "due_date": "2025-12-25"}`
  - Response: `{"id": "...", "title": "...", "status": "open", "due_date": "...", "created_at": "..."}`
- `GET /tasks` — list user's tasks (paginated, filtered)
  - Query: `limit=20&offset=0&filter=open` (filters: all, open, completed, overdue)
  - Response: `{"tasks": [...], "total": 42, "overdue_count": 2}`
- `GET /tasks/{id}` — get task details
  - Response: full task object
- `PATCH /tasks/{id}` — update task
  - Request: `{"title": "...", "description": "...", "due_date": "...", "completed": true/false}`
  - Response: updated task object
- `DELETE /tasks/{id}` — soft delete task
  - Response: `204 No Content`
- `POST /tasks/{id}/complete` — mark task completed (convenience endpoint)
  - Response: `{"id": "...", "completed_at": "2025-01-15T10:00:00Z"}`
- `POST /tasks/{id}/reopen` — mark task incomplete (undo completion)
  - Response: task object with `completed_at: null`

**Backend — Task Filtering & Sorting**
- Filters: `all`, `open` (not completed), `completed`, `overdue` (due_date < today and not completed)
- Sorting: by due_date (nearest first), then by creation date
- Overdue count in list response for UI indicators

**Backend — Task Validation**
- Title: required, max 255 chars
- Description: optional, max 2000 chars
- Due date: optional, but if provided must be date or datetime
- No validation that due_date is in future (allow past dates for historical tasks)

**Backend — Testing**
- Unit tests: Task model creation
- Integration tests: `/tasks` CRUD endpoints
  - Create task, verify stored
  - List tasks with filters (all, open, completed, overdue)
  - Update task details
  - Mark completed/reopen
  - Soft delete
- Integration tests: filtering logic
  - Create 5 tasks with various due dates
  - Filter by completed, open, overdue
  - Verify counts and sorting

**Android — Tasks Screen**
- `TasksScreen.kt` — tab in main app
  - Task list (scrollable, lazy-loaded)
  - Filter buttons: "All", "Open", "Completed", "Overdue"
  - Floating action button (FAB) to create new task
  - Each task shows: title, due date, status (completed/open)
  - Tasks sorted by due date (nearest first)
  - Overdue tasks highlighted in red/orange
- `TaskCard.kt` — composable for individual task
  - Display title, due date, completion status
  - Tap to open details
  - Swipe/long-press for quick actions (complete, delete)
  - Checkbox to mark complete (immediate action)

**Android — Create/Edit Task Screen**
- `TaskFormScreen.kt` — form for creating/editing task
  - Title field (required, autofocus)
  - Description field (optional, multiline)
  - Date picker for due date (optional)
  - Save button
  - Cancel button
  - Delete button (if editing existing task)
- Date picker: use Android's standard `DatePicker` or Material date picker
- Validation: enforce required fields, show error toast if invalid

**Android — Task Completion UX**
- Checkbox in TaskCard to quickly mark complete (no extra screen)
- Visual feedback: strikethrough or fade completed task
- Swipe gesture to complete (optional, nice-to-have)

**Android — Testing**
- Unit tests: Task CRUD (create, list, update, delete)
- Instrumented tests: TasksScreen UI
  - Create task through form
  - Verify appears in list
  - Mark complete
  - Filter by completed
  - Verify overdue indicator
  - Edit task
  - Delete task

### 2.2 Out of Scope

- Task reminders/notifications (deferred to M3)
- Task subtasks or dependencies
- Task categories/tags
- Task priority levels (can be added in M5+)
- Task recurring/repeating
- Task time estimates or time tracking
- Task assignment (collaboration)
- Task comments or notes (separate from description)
- Task attachment (files/images)
- Integration with calendar app

---

## 3. Database Schema (new tables)

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date DATE,
    completed_at TIMESTAMP,  -- NULL if not yet completed
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,  -- soft delete
    INDEX idx_user_due_date (user_id, due_date),
    INDEX idx_user_completed (user_id, completed_at),
    INDEX idx_user_deleted (user_id, deleted_at)
);
```

---

## 4. Task Breakdown (execution order)

### Backend

1. Create Task model + Alembic migration
2. Implement task CRUD endpoints (`/tasks` POST, GET, PATCH, DELETE)
3. Implement task filtering (open, completed, overdue)
4. Implement task sorting (by due date)
5. Implement quick-action endpoints (`/tasks/{id}/complete`, `/tasks/{id}/reopen`)
6. Write backend tests (CRUD + filtering)
7. Document task endpoint behavior and edge cases

### Android

8. Create TasksScreen + TaskCard composables
9. Create TaskFormScreen (create/edit task)
10. Implement task CRUD API calls (integrate with endpoints)
11. Implement filtering UI (filter buttons)
12. Add date picker for due date selection
13. Implement task completion checkbox
14. Add overdue indicator/styling
15. Write Android tests

### Integration

16. End-to-end test: create task → see in list → mark complete → filter by completed
17. End-to-end test: edit task → due date changes → resort
18. End-to-end test: delete task → soft delete (can add recovery later)

---

## 5. Task Filtering Logic (backend)

```python
def get_tasks(user_id: str, filter: str = "all", limit: int = 20, offset: int = 0):
    query = Task.query.filter_by(user_id=user_id, deleted_at=None)
    
    if filter == "open":
        query = query.filter(Task.completed_at.is_(None))
    elif filter == "completed":
        query = query.filter(Task.completed_at.is_not(None))
    elif filter == "overdue":
        query = query.filter(
            Task.completed_at.is_(None),
            Task.due_date < today()
        )
    
    # Sort by due date (nearest first), then creation date
    query = query.order_by(Task.due_date.asc(), Task.created_at.asc())
    
    total = query.count()
    tasks = query.offset(offset).limit(limit).all()
    overdue_count = Task.query.filter_by(
        user_id=user_id, 
        deleted_at=None
    ).filter(Task.due_date < today(), Task.completed_at.is_(None)).count()
    
    return {"tasks": tasks, "total": total, "overdue_count": overdue_count}
```

---

## 6. Acceptance Criteria (Definition of Done for Sprint 04)

- [ ] Task model created, migrations applied
- [ ] `/tasks` POST endpoint creates task
- [ ] `/tasks` GET endpoint lists tasks (paginated)
- [ ] Task filtering works: all, open, completed, overdue
- [ ] Task sorting works: by due_date (nearest first)
- [ ] `/tasks/{id}` PATCH endpoint updates task
- [ ] `/tasks/{id}` DELETE endpoint soft-deletes task
- [ ] `/tasks/{id}/complete` marks task completed
- [ ] `/tasks/{id}/reopen` marks task incomplete
- [ ] Overdue count included in list response
- [ ] TasksScreen displays all tasks in list
- [ ] Filter buttons work (all, open, completed, overdue)
- [ ] TaskCard shows title, due date, completion status
- [ ] Checkbox to mark complete works immediately
- [ ] Overdue tasks highlighted visually
- [ ] TaskFormScreen creates new task
- [ ] TaskFormScreen edits existing task
- [ ] Date picker works for due_date selection
- [ ] Task deletion removes from list (soft delete)
- [ ] All backend tests pass
- [ ] All Android tests pass
- [ ] End-to-end: create → complete → filter works
- [ ] No regressions in Chat or Memory
- [ ] CI pipeline passes

---

## 7. Example Task Workflow

```
User opens Tasks tab → sees empty list
User taps FAB → TaskFormScreen opens
User enters: title="Buy groceries", due_date="2025-01-20"
User saves → task appears in list

Days pass...
User opens Tasks → sees "Buy groceries" at top (nearest due date)
User taps checkbox → task marked complete, fades
User filters to "Completed" → sees "Buy groceries" crossed out

If due_date had been today or earlier:
Task would appear in red/orange in "Overdue" filter
```

---

## 8. Due Date Display Format

- **In list:** "Jan 20" or "Today" or "Tomorrow" or "Overdue"
- **In form:** Standard date picker (platform default)
- **In details:** "Due on January 20, 2025"
- **Overdue:** "Due Jan 15 (Overdue by 5 days)" or similar

---

## 9. Nice-to-Have Polish (can be added after Sprint 04)

- Swipe to complete (Android native gesture)
- Undo delete (keep soft-deleted tasks recoverable for 30 days)
- Task sort options (due date, creation date, alphabetical)
- Quick-add task from chat ("Create task: Buy milk")
- Task count badge on Tasks tab
- Calendar view of tasks (separate screen, M5+)

---

## 10. Exit Condition

Sprint 04 is complete when:
- Users can create, read, update, delete tasks
- Task list is accessible with filters and sorting
- All tests pass
- CI pipeline passes
- M2 is feature-complete (Chat + Memory + Tasks)

---

## 11. M2 Complete Checklist

Once Sprint 04 closes:

- [x] Users can chat with Raghvi (Sprint 02)
- [x] Users can save and manage memories (Sprint 03)
- [x] Users can create and manage tasks (Sprint 04)
- [x] All endpoints protected via JWT auth (M1 foundation)
- [x] All backends tests pass
- [x] All Android tests pass
- [x] CI pipeline passes
- [ ] Reminders for tasks (deferred to M3)
- [ ] Raghvi proactive briefings (M3)
- [ ] Android device actions (M4)

**M2 is production-ready for beta testing (internal or closed group)**