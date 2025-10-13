from ReDNACoreDemo.core.head_coach.tool_manager import ToolManager


def test_tool_manager_lists_active_tools(tmp_path):
    registry_path = tmp_path / "tool_registry.json"
    registry_path.write_text(
        """
        {
          "tool_registry_version": "1.0",
          "tools": [
            {
              "tool_id": "demo_tool",
              "name": "Demo Tool",
              "category": "test",
              "description": "Example entry",
              "status": "active",
              "capabilities": [],
              "data_requirements": [],
              "user_permissions_required": [],
              "integration_points": {},
              "module": "ReDNACoreDemo.core.head_coach.tools.financial_planner",
              "class": "FinancialPlanner"
            }
          ]
        }
        """.strip()
    )

    manager = ToolManager(registry_path=registry_path)
    tools = manager.list_tools()
    assert len(tools) == 1
    assert tools[0].tool_id == "demo_tool"


def test_tool_manager_instantiates_tool(tmp_path):
    registry_path = tmp_path / "tool_registry.json"
    registry_path.write_text(
        """
        {
          "tool_registry_version": "1.0",
          "tools": [
            {
              "tool_id": "financial_planner",
              "name": "Financial Planner",
              "category": "life",
              "description": "Budget helper",
              "status": "active",
              "capabilities": [],
              "data_requirements": [],
              "user_permissions_required": [],
              "integration_points": {},
              "module": "ReDNACoreDemo.core.head_coach.tools.financial_planner",
              "class": "FinancialPlanner"
            }
          ]
        }
        """.strip()
    )

    manager = ToolManager(registry_path=registry_path)
    tool = manager.get_tool("financial_planner", user_id="user123")
    from ReDNACoreDemo.core.head_coach.tools.financial_planner import FinancialPlanner

    assert isinstance(tool, FinancialPlanner)
