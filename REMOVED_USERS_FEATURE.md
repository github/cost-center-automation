# Full Sync Mode - Removed Users Feature

## Overview

This feature automatically detects and removes users from cost centers when they're no longer members of the corresponding GitHub team. This "full sync" mode ensures cost centers stay perfectly synchronized with actual team membership.

## Why This Feature?

When teams change over time (members leave, are removed, or switch teams), their cost center assignments can become stale. This feature keeps cost centers synchronized with actual team membership by:

1. **Detecting** users in cost centers who are no longer in the corresponding team
2. **Reporting** these users with warnings
3. **Automatically removing** them to maintain sync

## How It Works

### Detection Logic

For each cost center being managed:
1. Fetch the **expected members** from the GitHub team
2. Fetch the **current members** from the cost center API
3. Calculate users no longer in teams: `current_members - expected_members`
4. Log warnings for any users found who left teams

### Removal Logic (when enabled)

If `teams.remove_users_no_longer_in_teams: true` (default):
- Automatically remove users who left teams from their cost centers
- Log success/failure for each removal
- Provide summary statistics

## Configuration

### Enable/Disable

Add to `config/config.yaml`:

```yaml
teams:
  enabled: true
  scope: "enterprise"  # or "organization"
  mode: "auto"
  
  # Full sync mode
  remove_users_no_longer_in_teams: true  # Set to false to disable automatic removal
```

### Default Behavior

- **Default**: `true` (enabled - full sync mode)
- **When enabled**: Users who left teams are detected and automatically removed
- **When disabled**: Users who left teams are detected and logged but NOT removed

## Usage Examples

### Plan Mode (Preview)

```bash
# With full sync enabled (default)
python main.py --teams-mode --assign-cost-centers --mode plan

# Output shows:
# MODE=plan: Full sync mode is ENABLED
# In apply mode, users no longer in teams will be removed from cost centers
# (Cannot show specific removed users in plan mode - cost centers don't exist yet)
```

```bash
# With full sync disabled in config
python main.py --teams-mode --assign-cost-centers --mode plan

# Output shows:
# MODE=plan: Full sync mode is DISABLED
# Users in cost centers but not in teams will remain assigned
```

### Apply Mode (Execution)

```bash
# Apply with full sync enabled (default)
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Output includes:
# [INFO] Checking for users in cost centers who are no longer in teams...
# [WARNING] ⚠️  Found 3 users no longer in team for cost center '[enterprise team] Frontend'
# [WARNING]    ⚠️  alice is in cost center but not in team
# [WARNING]    ⚠️  bob is in cost center but not in team
# [INFO] Removing 3 users from '[enterprise team] Frontend'...
# [INFO] ✅ Successfully removed 3 users from cost center
# [INFO] 📊 Removed users summary: Found 3 users no longer in teams, successfully removed 3
```

```bash
# Apply with full sync disabled
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Adds users to cost centers but leaves users who left teams alone
```

## API Methods Added

### 1. `get_cost_center_members(cost_center_id)`

**Purpose**: Fetch current members of a cost center

**Endpoint**: `GET /enterprises/{enterprise}/settings/billing/cost-centers/{cost_center_id}`

**Returns**: List of usernames currently assigned to the cost center

**Example**:
```python
members = github_manager.get_cost_center_members("abc-123-def")
# Returns: ['alice', 'bob', 'charlie']
```

### 2. `remove_users_from_cost_center(cost_center_id, usernames)`

**Purpose**: Remove multiple users from a cost center

**Endpoint**: `DELETE /enterprises/{enterprise}/settings/billing/cost-centers/{cost_center_id}/resource`

**Parameters**:
- `cost_center_id`: ID of the cost center
- `usernames`: List of usernames to remove

**Returns**: Dict mapping username → success status (True/False)

**Example**:
```python
results = github_manager.remove_users_from_cost_center(
    "abc-123-def", 
    ["alice", "bob"]
)
# Returns: {'alice': True, 'bob': True}
```

## Implementation Details

### Files Modified

1. **`src/github_api.py`**
   - Added `get_cost_center_members()` method
   - Added `remove_users_from_cost_center()` method

2. **`src/config_manager.py`**
   - Added `teams_remove_users_no_longer_in_teams` configuration property
   - Backward compatibility with old `remove_orphaned_users` key

3. **`src/teams_cost_center_manager.py`**
   - Added `_remove_users_no_longer_in_teams()` private method
   - Modified `sync_team_assignments()` to call removed user detection
   - Added removed user handling in apply mode

4. **`config/config.yaml` & `config/config.example.yaml`**
   - Added `remove_users_no_longer_in_teams` configuration option with documentation

5. **`main.py`**
   - Display full sync mode status in configuration output

### Logging

The feature provides comprehensive logging:

- **INFO**: General operation status
- **WARNING**: Users no longer in teams detected
- **ERROR**: API failures or removal failures
- **DEBUG**: Detailed member counts

### Error Handling

- API failures are logged but don't stop execution
- Individual user removal failures are tracked separately
- Summary statistics show success/failure counts

## Use Cases

### Use Case 1: Team Restructuring

**Scenario**: Your engineering team is split into "Frontend" and "Backend" teams. Some engineers move from one team to another.

**Without this feature**:
- Users remain in their old cost center
- Cost reporting is inaccurate
- Manual cleanup required

**With full sync mode**:
```yaml
teams:
  remove_users_no_longer_in_teams: true  # Default
```
- Users automatically removed from old cost center
- Added to new cost center
- Cost reporting stays accurate

### Use Case 2: Employee Departures

**Scenario**: Team members leave the company and are removed from GitHub teams.

**Without this feature**:
- Departed users remain in cost centers
- Inflated cost center counts
- Security/audit concerns

**With this feature**:
- Departed users automatically removed from cost centers
- Accurate headcount per cost center
- Clean audit trail

### Use Case 3: Temporary Team Assignments

**Scenario**: Users temporarily join teams for projects, then return to their main team.

**With this feature enabled**:
- Users are automatically moved back when they leave the temporary team
- No manual cleanup needed

## Best Practices

### 1. Test in Plan Mode First

Always run with `--mode plan` to see what changes would be made:

```bash
python main.py --teams-mode --assign-cost-centers --mode plan
```

### 2. Test Before Enabling Full Sync

If you want to see users who left teams without removing them first:

```bash
# Step 1: Disable full sync temporarily
# Set remove_users_no_longer_in_teams: false in config

# Step 2: Run once to see users who left (they'll be logged as warnings)
python main.py --teams-mode --assign-cost-centers --mode apply --yes

# Step 3: Review logs for users who left teams
# Step 4: If comfortable, enable full sync (set to true)
# Step 5: Run again with full sync enabled
```

### 3. Regular Sync Schedule

Run teams sync regularly to keep cost centers up-to-date:

```bash
# Daily cron job
0 2 * * * cd /path/to/repo && python main.py --teams-mode --assign-cost-centers --mode apply --yes
```

### 4. Monitor Logs

Review execution logs for:
- Number of users who left teams found
- Removal success rates
- Any API errors

### 5. Consider Impact

Full sync mode is enabled by default. Before using it, consider:
- Do you have users manually added to cost centers outside of team membership?
- Are there legitimate reasons for users to be in cost centers but not teams?
- Do you have adequate logging/monitoring?

## Limitations

1. **Plan Mode**: Cannot show specific users who left teams in plan mode because cost centers may not exist yet. Detection only runs in apply mode after cost centers are created/resolved.

2. **Manual Assignments**: If you manually add users to cost centers outside of this tool, they will be detected as "not in team" and removed if they're not in the corresponding team.

3. **API Rate Limits**: Checking cost center membership adds API calls. Large numbers of cost centers may hit rate limits.

4. **Single Cost Center**: Remember, users can only belong to ONE cost center at a time (GitHub API constraint).

## Troubleshooting

### Users who left teams not being removed

**Check**:
1. Is `remove_users_no_longer_in_teams: true` in config? (Should be default)
2. Running in `--mode apply` (not plan)?
3. Check logs for API errors

### False positives (users incorrectly identified as having left)

**Cause**: User is not in the team being synced

**Solutions**:
- Verify team membership in GitHub
- Check that correct teams are configured
- Review team mappings in manual mode

### API 404 errors when checking cost center members

**Cause**: Cost center doesn't exist yet (plan mode issue)

**Solution**: This is expected in plan mode. Detection only runs in apply mode.

## Future Enhancements

Potential improvements:
1. **Dry-run for removed users**: Show what would be removed without actually removing
2. **Whitelist**: Configure specific users to never be removed
3. **Notification**: Send alerts when users who left teams are found/removed
4. **Audit log export**: Export removed user reports to CSV

## Summary

The full sync mode (removed users feature) helps maintain clean, accurate cost center assignments by:

- ✅ **Detecting** users who left teams but are still in cost centers
- ✅ **Reporting** discrepancies with clear warnings  
- ✅ **Removing** users who left teams automatically (enabled by default)
- ✅ **Working** with both organization and enterprise team scopes
- ✅ **Configurable** - disable if needed
- ✅ **Safe** - clear logging, error handling, backward compatible

This keeps your cost center data synchronized with actual team membership over time with minimal manual intervention.
