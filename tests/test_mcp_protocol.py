import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class McpProtocolTests(unittest.TestCase):
    def _tool_names(
        self, command: str, *, args: list[str], cwd: Path, state_home: Path
    ) -> set[str]:
        async def exercise_server() -> set[str]:
            parameters = StdioServerParameters(
                command=command,
                args=args,
                cwd=cwd,
                env={
                    **os.environ,
                    "SMS_CLI_MODEM_ID": "6",
                    "XDG_STATE_HOME": str(state_home),
                },
            )
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    return {tool.name for tool in tools.tools}

        return asyncio.run(exercise_server())

    def test_stdio_server_advertises_safe_tool_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_names = self._tool_names(
                sys.executable,
                args=["-m", "sms_cli.mcp_server"],
                cwd=Path(__file__).parent.parent, state_home=Path(temp_dir)
            )

        self.assertEqual(
            tool_names,
            {
                "get_modem_status",
                "list_messages",
                "read_message",
                "get_credit",
                "list_packages",
                "get_package_status",
                "prepare_send_sms",
                "confirm_send_sms",
                "prepare_package_action",
                "confirm_package_action",
            },
        )

    def test_installed_server_advertises_tools_over_stdio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            environment = root / "environment"
            subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
            subprocess.run(
                [environment / "bin" / "pip", "install", "."],
                cwd=Path(__file__).parent.parent,
                check=True,
            )
            tool_names = self._tool_names(
                str(environment / "bin" / "smscp"),
                args=[],
                cwd=Path(__file__).parent.parent,
                state_home=root / "state",
            )

        self.assertIn("prepare_send_sms", tool_names)
        self.assertIn("confirm_package_action", tool_names)


if __name__ == "__main__":
    unittest.main()
