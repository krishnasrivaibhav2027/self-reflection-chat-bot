# Planner Node Implementation Summary

## ✅ What Was Implemented

### **1. New Schema (`backend/chatbot/schemas.py`)**
Added `ImplementationPlan` schema:
```python
class ImplementationPlan(BaseModel):
    dependencies: List[str]  # Pip packages to install
    logic_steps: List[str]   # Implementation steps
    complexity: Literal["simple", "moderate", "complex"]
    edge_cases: List[str]    # Cases to handle
    approach: str            # Algorithm description
```

### **2. New Prompt (`backend/prompts/planning.py`)**
Created planning prompt that uses structured output to generate implementation plans.

### **3. Updated Graph Workflow (`backend/chatbot/graph_workflow.py`)**

#### Added to ChatState:
```python
plan: dict  # ImplementationPlan as dict
dependencies: List[str]  # Dependencies to install
```

#### Nodes Using Structured Output:
1. **router_node** - Uses `.with_structured_output(QueryIntent)` ✅
2. **planner_node** - Uses `.with_structured_output(ImplementationPlan)` ✅

#### Nodes Using StrOutputParser (Plain Text):
1. **conversation_node** - Returns conversational text
2. **coding_node** - Returns Python code as text
3. **code_tester_node** - Returns pytest code as text (gets dependencies from state)
4. **code_reflection_node** - Returns reflection text

#### Updated Workflow:
```
Router (structured) → Planner (structured) → Coding (text) → Tester (text + uses deps from state) → Reflection (text) → Review
```

## 🎯 How It Works

### Flow:
1. **User submits coding query**
2. **Router** classifies intent using **structured output** → Returns `QueryIntent`
3. **Planner** analyzes requirements using **structured output** → Returns `ImplementationPlan`
   - Sets `state.dependencies` 
   - Sets `state.plan`
4. **Coding** node generates code as plain text
5. **Tester** retrieves `dependencies` from state and passes to sandbox
6. **Reflection** analyzes failures as plain text
7. **Review** gets human approval

### Key Benefits:
- ✅ Automatic dependency detection (via planner structured output)
- ✅ No JSON parsing errors in router and planner
- ✅ Type-safe intent and plan data
- ✅ Code/tests remain as readable plain text

## 📊 Structured Output vs Plain Text

### When We Use Structured Output:
- **Router** - Need validated intent classification
- **Planner** - Need validated plan with dependencies list

### When We Use Plain Text:
- **Code generation** - Code should be plain text
- **Test generation** - Tests should be plain text
- **Reflection** - Reasoning should be plain text
- **Conversation** - Chat responses should be plain text

## 🎉 Benefits

### Before:
```
Query → Coding → Test (fails if needs external packages) → Reflect → Retry
```

### After:
```
Query → Plan (structured: detect deps) → Coding → Test (uses deps from state) → Success!
```

### Impact:
- **Fewer test failures** due to missing dependencies
- **Smarter code generation** with implementation plan
- **Type-safe structured data** for router and planner only
- **Readable code/text** for everything else

## 🚀 Summary

**Structured output is used in 2 nodes:**
1. Router (QueryIntent)
2. Planner (ImplementationPlan)

**Plain text is used in 5 nodes:**
1. Conversation
2. Coding
3. Code Tester (but uses dependencies from planner's state)
4. Code Reflection
5. Final Response

This is the correct balance - structured data where needed, readable text everywhere else!
