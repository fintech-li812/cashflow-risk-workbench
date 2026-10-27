"""MCP stdio entry, fixed trusted scope via environment; no arbitrary SQL or paths."""
from mcp.server.fastmcp import FastMCP
from config import Config
from service import Service

mcp=FastMCP('manufacturing-cashflow-v1-candidate')

def service():return Service(Config.from_env())

@mcp.tool()
def read_cashflow_result() -> dict:
    """Read the configured approved cashflow snapshot. Never calculate forecasts."""
    return service().read()

@mcp.tool()
def save_cashflow_result(result:dict, request_id:str) -> dict:
    """Commit the exact approved result to MySQL; replay same request safely."""
    return service().save(result,request_id)

@mcp.tool()
def query_cashflow_result(request_id:str,period:str,source_revision:str,run_id:str) -> dict:
    """Exact query within configured tenant/company and supplied version context."""
    return service().query(request_id,period,source_revision,run_id)

if __name__=='__main__':mcp.run(transport='stdio')
