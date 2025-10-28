# Budget System Improvements for Repository Cost Center Assignment

## Overview
This document outlines the budget system improvements needed for the repository cost center assignment feature to support multiple products and be more resilient.

## Current Implementation Issues
1. **Hardcoded Budget Amount**: `create_cost_center_budget()` uses hardcoded $0 amounts
2. **Missing Actions Support**: No support for Actions product budgets
3. **Limited Product Support**: Only supports Copilot PRU budgets
4. **Manual Budget Type Selection**: No abstraction for different budget types

## Proposed Improvements

### 1. **Configurable Budget Amounts**
```python
def create_cost_center_budget(self, cost_center_id: str, cost_center_name: str, budget_amount: int = 100) -> bool:
    # Instead of hardcoded budget_amount: 0
```

### 2. **Product-Agnostic Budget Creation**
```python
def create_product_budget(self, cost_center_id: str, cost_center_name: str, product: str, amount: int) -> bool:
    """
    Create a product-level budget for a cost center.
    
    Args:
        cost_center_id: UUID of the cost center
        cost_center_name: Name of the cost center (for logging)
        product: Product name (e.g., 'actions', 'copilot', 'packages')
        amount: Budget amount in dollars
    """
    # Dynamic budget type selection based on product
    budget_type = self._get_budget_type_for_product(product)
    product_sku = self._get_product_sku(product)
```

### 3. **Product Registry System**
```python
# Configuration-driven product support
SUPPORTED_PRODUCTS = {
    'actions': {
        'budget_type': 'ProductPricing',
        'sku': 'actions',
        'default_amount': 125
    },
    'copilot': {
        'budget_type': 'SkuPricing', 
        'sku': 'copilot_premium_request',
        'default_amount': 100
    },
    'packages': {
        'budget_type': 'ProductPricing',
        'sku': 'packages',
        'default_amount': 50
    },
    'codespaces': {
        'budget_type': 'ProductPricing',
        'sku': 'codespaces',
        'default_amount': 200
    }
}
```

### 4. **Budget Existence Checking**
```python
def check_cost_center_has_product_budget(self, cost_center_id: str, cost_center_name: str, product: str) -> bool:
    """Check if a cost center already has a budget for a specific product."""
```

### 5. **Configuration-Driven Budget Management**
```yaml
# config.yaml extension
budgets:
  enabled: true
  products:
    - name: copilot
      amount: 100
      enabled: true
    - name: actions  
      amount: 125
      enabled: true
    - name: packages
      amount: 50
      enabled: false
```

## Implementation Priority

### Phase 1 (Critical - Include in current PR)
- ✅ Fix configurable budget amounts
- ✅ Add Actions product budget support
- ✅ Add budget existence checking

### Phase 2 (Future Enhancement)  
- 🔄 Product registry system
- 🔄 Configuration-driven budget management
- 🔄 Support for additional products (Packages, Codespaces)

### Phase 3 (Advanced Features)
- 🔄 Budget alerting and monitoring
- 🔄 Cost allocation reporting
- 🔄 Budget approval workflows

## Benefits
1. **Extensibility**: Easy to add new products without code changes
2. **Configurability**: Customers can customize budget amounts per product
3. **Resilience**: Handles API changes better with abstracted product definitions
4. **Maintainability**: Centralized product configuration reduces duplication