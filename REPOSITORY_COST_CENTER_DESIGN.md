# Repository Cost Center Assignment - Design Document

## Overview

This feature enables automatic assignment of repositories to cost centers based on repository custom properties. This complements the existing user-based and team-based assignment modes.

## API Endpoints Required

### Organization-Level Custom Properties
- `GET /orgs/{org}/properties/schema` - Get all custom property definitions
- `GET /orgs/{org}/properties/values` - List all repositories with their custom property values

### Repository-Level Custom Properties
- `GET /repos/{owner}/{repo}/properties/values` - Get custom properties for a specific repo

### Permissions Required
- **Read**: "Custom properties" organization permissions (read)
- **Write**: "Metadata" repository permissions (read) to add repos to cost centers

## Implementation Approach

### Mode 1: Auto-Discovery Mode (Recommended)
Automatically discover repositories based on a specific custom property and map values to cost centers.

**Configuration Example:**
```yaml
github:
  cost_centers:
    mode: repository  # New mode
    repository_config:
      property_name: "cost-center"  # The custom property to use
      auto_create_cost_centers: true  # Create cost centers if they don't exist
      prefix: ""  # Optional prefix for cost center names
      
      # Optional: Manual overrides for specific property values
      property_value_mapping:
        "engineering": "Engineering Team"
        "marketing": "Marketing Department"
```

**Behavior:**
1. Fetch all repositories in the organization with their custom properties
2. Filter repositories that have the specified property (e.g., "cost-center")
3. Group repositories by property value
4. For each unique property value:
   - Check if cost center exists (or create if `auto_create_cost_centers: true`)
   - Add all repositories with that value to the cost center

**Example:**
- Repository `app-frontend` has property `cost-center: "engineering"`
- Repository `app-backend` has property `cost-center: "engineering"`
- Repository `website` has property `cost-center: "marketing"`

Results in:
- Cost center "engineering" (or "Engineering Team" if mapped) with 2 repos
- Cost center "marketing" (or "Marketing Department" if mapped) with 1 repo

### Mode 2: Explicit Mapping Mode
Manually define which property values map to which cost centers.

**Configuration Example:**
```yaml
github:
  cost_centers:
    mode: repository
    repository_config:
      property_name: "team"
      explicit_mappings:
        - cost_center: "Platform Engineering"
          property_values: ["platform", "infrastructure", "devops"]
          
        - cost_center: "Product Development"
          property_values: ["frontend", "backend", "mobile"]
          
        - cost_center: "Data Science"
          property_values: ["ml", "analytics", "data"]
```

**Behavior:**
1. For each explicit mapping:
   - Get the cost center by name (create if doesn't exist)
   - Fetch all repositories with property values in the mapping list
   - Add repositories to the cost center

### Mode 3: Query-Based Mode (Advanced)
Use GitHub's repository search query syntax to find repositories.

**Configuration Example:**
```yaml
github:
  cost_centers:
    mode: repository
    repository_config:
      cost_center_queries:
        - cost_center: "Production Services"
          query: "custom_properties:environment:production"
          
        - cost_center: "Development Services"
          query: "custom_properties:environment:development custom_properties:environment:staging"
```

**Note:** The `repository_query` parameter in `/orgs/{org}/properties/values` accepts GitHub search qualifiers.

## Technical Implementation

### 1. New Module: `src/repository_cost_center_manager.py`

```python
class RepositoryCostCenterManager:
    """Manages cost center assignments based on repository custom properties."""
    
    def __init__(self, config, github_api):
        self.config = config
        self.github_api = github_api
        self.logger = logging.getLogger(__name__)
    
    def get_all_repository_properties(self, org: str) -> list:
        """Fetch all repositories with their custom property values."""
        # GET /orgs/{org}/properties/values (paginated)
        
    def get_repository_properties(self, owner: str, repo: str) -> list:
        """Get custom properties for a specific repository."""
        # GET /repos/{owner}/{repo}/properties/values
    
    def get_custom_property_schema(self, org: str) -> list:
        """Get all custom property definitions for the organization."""
        # GET /orgs/{org}/properties/schema
    
    def auto_discover_mode(self, org: str):
        """Auto-discover repositories by property and create/update cost centers."""
        # Implementation for Mode 1
    
    def explicit_mapping_mode(self, org: str):
        """Map repositories to cost centers using explicit mappings."""
        # Implementation for Mode 2
    
    def query_based_mode(self, org: str):
        """Find repositories using search queries and assign to cost centers."""
        # Implementation for Mode 3
    
    def assign_repositories_to_cost_center(self, cost_center_id: str, repositories: list):
        """Assign multiple repositories to a cost center."""
        # Batch repository assignment
```

### 2. Extend `src/github_api.py`

Add new methods for custom properties:

```python
def get_org_custom_properties(self, org: str) -> dict:
    """Get all custom property definitions for an organization."""
    url = f"{self.base_url}/orgs/{org}/properties/schema"
    return self._make_request("GET", url)

def get_org_repositories_with_properties(self, org: str, page: int = 1, per_page: int = 100, query: str = None) -> dict:
    """Get all repositories with their custom property values."""
    url = f"{self.base_url}/orgs/{org}/properties/values"
    params = {"page": page, "per_page": per_page}
    if query:
        params["repository_query"] = query
    return self._make_request("GET", url, params=params)

def get_repository_custom_properties(self, owner: str, repo: str) -> dict:
    """Get custom properties for a specific repository."""
    url = f"{self.base_url}/repos/{owner}/{repo}/properties/values"
    return self._make_request("GET", url)
```

### 3. Update `main.py`

Add support for repository mode:

```python
if config.github_cost_centers_mode == 'repository':
    logger.info("Running in repository mode...")
    from src.repository_cost_center_manager import RepositoryCostCenterManager
    
    repo_manager = RepositoryCostCenterManager(config, github_api)
    
    # Determine which sub-mode based on config
    repo_config = config.github_cost_centers_repository_config
    
    if hasattr(repo_config, 'property_name') and not hasattr(repo_config, 'explicit_mappings'):
        repo_manager.auto_discover_mode(org_name)
    elif hasattr(repo_config, 'explicit_mappings'):
        repo_manager.explicit_mapping_mode(org_name)
    elif hasattr(repo_config, 'cost_center_queries'):
        repo_manager.query_based_mode(org_name)
    else:
        logger.error("Invalid repository mode configuration")
```

### 4. Configuration Schema Updates

Update `config/config.example.yaml`:

```yaml
github:
  cost_centers:
    # Mode can be: 'users' (default), 'teams', or 'repository'
    mode: repository
    
    # Configuration for repository mode
    repository_config:
      # Auto-discovery mode: Uses a single property to group repositories
      property_name: "cost-center"
      auto_create_cost_centers: true
      prefix: ""  # Optional prefix for cost center names (e.g., "Team " -> "Team Engineering")
      
      # Optional: Map property values to specific cost center names
      property_value_mapping:
        "eng": "Engineering"
        "product": "Product Development"
      
      # Explicit mapping mode: Define exact mappings
      # Uncomment to use this mode instead of auto-discovery
      # explicit_mappings:
      #   - cost_center: "Platform Engineering"
      #     property_values: ["platform", "infrastructure", "devops"]
      #   
      #   - cost_center: "Product Development"
      #     property_values: ["frontend", "backend", "mobile"]
      
      # Query-based mode: Use GitHub search queries
      # Uncomment to use this mode instead of auto-discovery
      # cost_center_queries:
      #   - cost_center: "Production Services"
      #     query: "custom_properties:environment:production"
      #   
      #   - cost_center: "Development Services"
      #     query: "custom_properties:environment:development"
```

## Data Flow

### Auto-Discovery Mode Flow

```
1. GET /orgs/{org}/properties/values
   → Returns: [
       {
         repository_id: 123,
         repository_name: "app-frontend",
         properties: [
           {property_name: "cost-center", value: "engineering"},
           {property_name: "team", value: "platform"}
         ]
       },
       ...
     ]

2. Filter repositories by configured property_name ("cost-center")

3. Group repositories by property value:
   engineering: [app-frontend, app-backend]
   marketing: [website, landing-page]

4. For each group:
   a. Check if cost center exists (or create)
   b. POST /copilot/usage/cost_centers/{cost_center_id}/repositories
      with batch of repository IDs
```

## Error Handling

1. **Missing Custom Property**: Skip repositories that don't have the configured property
2. **Invalid Property Value**: Log warning and skip
3. **Cost Center Creation Failure**: If `auto_create_cost_centers: false`, log error and skip
4. **Repository Assignment Failure**: Log error but continue with other repositories
5. **API Rate Limiting**: Implement exponential backoff and retry logic

## Logging Strategy

```
INFO: Found 150 repositories in organization 'acme-corp'
INFO: Filtering repositories with custom property 'cost-center'
INFO: Found 120 repositories with cost-center property
INFO: Discovered 5 unique cost center values: engineering, marketing, sales, support, operations
INFO: Processing cost center 'engineering' with 45 repositories
INFO: Cost center 'engineering' already exists (ID: cc_abc123)
INFO: Adding 45 repositories to cost center 'engineering'
INFO: Successfully added 45 repositories to cost center 'engineering'
INFO: Processing cost center 'marketing' with 30 repositories
WARNING: Cost center 'marketing' does not exist and auto_create is disabled, skipping
...
```

## Testing Strategy

1. **Unit Tests**: Mock API responses for custom properties endpoints
2. **Integration Tests**: Test with actual GitHub API (test organization)
3. **Test Scenarios**:
   - Repositories with different property values
   - Repositories missing the configured property
   - Empty organization (no repositories)
   - Large organization (pagination handling)
   - Cost centers that don't exist (auto-create enabled/disabled)

## Migration Path

Users currently using `users` or `teams` mode can migrate to `repository` mode by:

1. Setting up custom properties in their organization
2. Assigning property values to repositories
3. Updating configuration to use `mode: repository`
4. Running the tool to validate assignments
5. Switching over completely

## Future Enhancements

1. **Hybrid Mode**: Combine repository + team assignments in a single run
2. **Scheduled Property Sync**: Watch for repository property changes via webhooks
3. **Budget Allocation by Repository Count**: Auto-calculate budgets based on number of repos
4. **Property Validation**: Validate that repositories have required properties before assignment
5. **Dry-Run Mode**: Preview what changes would be made without applying them

## Implementation Priority

**Phase 1 (MVP)**:
- [ ] Extend `github_api.py` with custom properties endpoints
- [ ] Create `repository_cost_center_manager.py` with auto-discovery mode
- [ ] Update configuration schema
- [ ] Update `main.py` to support repository mode
- [ ] Basic logging and error handling

**Phase 2 (Enhanced)**:
- [ ] Add explicit mapping mode
- [ ] Add property value mapping feature
- [ ] Comprehensive error handling
- [ ] Unit tests

**Phase 3 (Advanced)**:
- [ ] Query-based mode
- [ ] Dry-run mode
- [ ] Documentation and examples
- [ ] Integration tests with real API

## Open Questions

1. **Batch Size**: What's the optimal batch size for repository assignments? (GitHub allows max 30 repos per batch in some endpoints)
2. **Pagination**: Should we fetch all repositories at once or paginate? (Large orgs may have thousands of repos)
3. **Caching**: Should we cache custom property schemas to reduce API calls?
4. **Conflict Resolution**: What happens if a repository is already in a different cost center?
