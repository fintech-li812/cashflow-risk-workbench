"""Same three tools over official MCP stdio or embedded Streamable HTTP."""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from config import Config
from service import Service
from workbench import project_status,list_sources,inspect_source,readiness

def build_mcp(port=18765):
    security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=[f'127.0.0.1:{port}',f'localhost:{port}'],
        allowed_origins=[f'http://127.0.0.1:{port}',f'http://localhost:{port}'])
    server=FastMCP('manufacturing-workbench-integration-v1',host='127.0.0.1',port=port,
        stateless_http=True,json_response=True,streamable_http_path='/',
        max_request_body_size=512000,transport_security=security)
    def service():return Service(Config.from_env())
    @server.tool()
    def get_workbench_status() -> dict:
        """Actual integration status, fixture profile, database readiness and missing modules."""
        return project_status()
    @server.tool()
    def list_manufacturing_sources() -> dict:
        """List only explicitly registered manufacturing sources; never infer native sheet binding."""
        return list_sources()
    @server.tool()
    def inspect_manufacturing_source(source_id:str='manufacturing_sample_v1') -> dict:
        """Read pinned sample workbook ranges without editing or calculating. Not a native sheet API."""
        return inspect_source(source_id)
    @server.tool()
    def get_manufacturing_readiness(source_id:str='manufacturing_sample_v1') -> dict:
        """Identify source-specific gaps and stop false full-cashflow/save claims; no gate/forecast inference."""
        return readiness(source_id)
    @server.tool()
    def read_cashflow_result() -> dict:
        """Read the configured approved cashflow snapshot; never predict or infer missing values."""
        return service().read()
    @server.tool()
    def save_cashflow_result(result:dict,request_id:str) -> dict:
        """Commit exactly the approved snapshot to MySQL, preserving stable request idempotence."""
        return service().save(result,request_id)
    @server.tool()
    def query_cashflow_result(request_id:str,period:str,source_revision:str,run_id:str) -> dict:
        """Exact query in configured trusted tenant/company and requested source/run/period."""
        return service().query(request_id,period,source_revision,run_id)
    return server

if __name__=='__main__':build_mcp().run(transport='stdio')
