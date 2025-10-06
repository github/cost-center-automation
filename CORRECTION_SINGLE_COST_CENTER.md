# Correction: Single Cost Center Constraint

## Summary of Change

**Critical Clarification**: Users can only belong to **ONE cost center** at a time, not multiple cost centers.

## What Changed

### Previous (Incorrect) Understanding
- ❌ Users in multiple teams would be added to ALL corresponding cost centers
- ❌ This was documented as "multi-team support" allowing users in multiple cost centers

### Current (Correct) Understanding  
- ✅ Users can only belong to ONE cost center (GitHub API constraint)
- ✅ Users in multiple teams are assigned to the LAST team's cost center processed
- ✅ Previous cost center assignments are overwritten (not additive)

## Code Changes

### 1. `src/teams_cost_center_manager.py`

**Method: `build_team_assignments()`**

**Changed Logic:**
- Now tracks ONE assignment per user instead of multiple
- Uses `user_assignments: Dict[str, Tuple[str, str, str]]` to store final assignment
- Last team processed wins for multi-team users
- Logs **warnings** (not info) for multi-team conflicts

**Key Code Change:**
```python
# OLD: Add user to all cost centers
assignments[cost_center].append((username, org, team_slug))

# NEW: Track single assignment (last one wins)
user_assignments[username] = (cost_center, org, team_slug)
```

**Warning Output:**
```
⚠️  Found 3 users who are members of multiple teams. 
Each user can only belong to ONE cost center - the LAST team processed will determine their assignment.
  ⚠️  alice is in multiple teams [org/frontend, org/backend] → will be assigned to 'Team: Backend'
```

### 2. `main.py`

**Updated Confirmation Message:**
```python
print("NOTE: Each user can only belong to ONE cost center.")
print("Users in multiple teams will be assigned to the LAST team's cost center.")
```

**Updated Summary Output:**
```python
print(f"Note: Each user is assigned to exactly ONE cost center")
```

### 3. Documentation Files Updated

**Files Modified:**
- `README.md` - Updated Multi-Team Membership section
- `TEAMS_INTEGRATION.md` - Updated behavior notes and best practices
- `TEAMS_QUICKSTART.md` - Updated examples and troubleshooting
- `IMPLEMENTATION_SUMMARY.md` - Updated feature description

## New Behavior Examples

### Example 1: Multi-Team User (Auto Mode)

**Setup:**
- User `alice` is in teams: `frontend` and `backend`
- Processing order: frontend (first), backend (second)

**Result:**
```
Processing team frontend...
  alice → "Team: Frontend" (temporarily assigned)
Processing team backend...
  alice → "Team: Backend" (FINAL assignment - overwrites previous)

⚠️  WARNING: alice is in multiple teams [org/frontend, org/backend] 
    → will be assigned to 'Team: Backend'
```

### Example 2: Manual Mode with Conflicts

**Config:**
```yaml
teams:
  mode: "manual"
  team_mappings:
    "org/team-a": "Cost Center A"
    "org/team-b": "Cost Center B"
    "org/team-c": "Cost Center C"
```

**User `bob` in all three teams:**

**Result:**
- Bob will be assigned to "Cost Center C" (last in processing order)
- Warning logged showing the conflict and final assignment

## Best Practices (Updated)

### 1. Always Review Plan Mode
```bash
python main.py --teams-mode --assign-cost-centers --mode plan
```
**Look for warnings about multi-team users before applying.**

### 2. Understand Processing Order
- Teams are processed in the order returned by GitHub API
- For multi-team users, the last team determines the final cost center
- This order may not be predictable

### 3. Minimize Multi-Team Conflicts

**Option A: Use Manual Mode**
```yaml
teams:
  mode: "manual"
  team_mappings:
    "org/primary-team": "Primary Cost Center"
    # Only process primary teams, ignore secondary teams
```

**Option B: Clean Up Team Membership**
- Ensure users have one primary team for cost allocation
- Use GitHub teams for permissions, not cost allocation if structure is complex

### 4. Monitor Warning Logs

**Warning output tells you exactly what will happen:**
```
⚠️  alice is in multiple teams [org/frontend, org/mobile] 
    → will be assigned to 'Team: Mobile'
```

**Review these before applying to ensure expected behavior.**

## Migration Guide

If you were testing the previous version:

### 1. Expect Different Results
Users in multiple teams will now be in **ONE** cost center, not multiple.

### 2. Review Your Team Structure
- Identify users in multiple teams
- Decide which team should "own" each user for cost allocation
- Consider restructuring teams if needed

### 3. Test in Plan Mode
```bash
python main.py --teams-mode --assign-cost-centers --mode plan --verbose
```

### 4. Check Warning Logs
Look for lines like:
```
⚠️  Found N users who are members of multiple teams
```

## Technical Details

### Why This Constraint Exists

The GitHub Enterprise Cost Center API enforces that:
- A user can only be assigned to ONE cost center at a time
- Adding a user to a new cost center removes them from any previous cost center
- This is a limitation of the GitHub API, not our implementation

### How We Handle It

1. **Track final assignment per user**: Use a dictionary mapping username → (cost_center, org, team)
2. **Overwrite on each team**: Each team processing overwrites the previous assignment
3. **Warn about conflicts**: Log warnings for users in multiple teams
4. **Make it explicit**: Documentation and UI messages make the constraint clear

## Testing

### Verify the Changes

```bash
# Compile check
python -m py_compile src/teams_cost_center_manager.py main.py

# Test with plan mode
python main.py --teams-mode --assign-cost-centers --mode plan

# Look for warning messages about multi-team users
```

### Expected Warning Format

```
[WARNING] ⚠️  Found 5 users who are members of multiple teams. Each user can only belong to ONE cost center - the LAST team processed will determine their assignment.
[WARNING]   ⚠️  alice is in multiple teams [org/team-a, org/team-b] → will be assigned to 'Team: Team B'
[WARNING]   ⚠️  bob is in multiple teams [org/team-x, org/team-y, org/team-z] → will be assigned to 'Team: Team Z'
```

## Summary

✅ **Code Updated**: Logic now assigns each user to exactly ONE cost center
✅ **Warnings Added**: Clear warnings for multi-team users showing final assignment
✅ **Documentation Updated**: All docs reflect single cost center constraint
✅ **Testing Verified**: All Python files compile successfully

**Key Takeaway**: Users in multiple teams will be assigned to the LAST team's cost center processed. Review warning logs in plan mode to understand which cost center each multi-team user will be assigned to before applying.
