
import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.server"],
    )

    async with stdio_client(server) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()

            # Ask the server which tools it exposes.
            tool_response = await session.list_tools()

            print("\nAVAILABLE MCP TOOLS")
            print("=" * 55)

            for tool in tool_response.tools:
                print(f"- {tool.name}: {tool.description}")

            tool_names = ["discover_api_endpoints",
                          "generate_api_test_cases",
                          "execute_generated_api_tests",
                          "generate_ai_test_cases",
                          "execute_ai_generated_api_tests",
                          "execute_boundary_api_tests",
                          "generate_consolidated_report",
]

            for tool_name in tool_names:
                print(f"\n\n--- Calling {tool_name} ---")

                result = await session.call_tool(
                    tool_name,
                    {},
                )

                for item in result.content:
                    if item.type == "text":
                        try:
                            parsed = json.loads(item.text)
                            print(json.dumps(parsed, indent=2))
                        except json.JSONDecodeError:
                            print(item.text)

                if result.isError:
                    print(f"ERROR: MCP tool {tool_name} failed.")
                    break


if __name__ == "__main__":
    asyncio.run(main())
