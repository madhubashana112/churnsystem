from typing import Dict, List
from churn_platform.domain.interfaces.i_schema_resolver import ISchemaResolver
from churn_platform.domain.models.schema_mapping import SchemaMapping, TableClassification
from churn_platform.infrastructure.ai.qwen_gateway import QwenGateway
from churn_platform.infrastructure.ai.prompts.schema_resolver_prompts import SCHEMA_RESOLVER_SYSTEM_PROMPT
import json

class AISchemaResolver(ISchemaResolver):
    def __init__(self, gateway: QwenGateway):
        self.gateway = gateway

    async def resolve(self, file_samples: Dict[str, str]) -> SchemaMapping:
        user_prompt = f"Analyze these file samples:\n{json.dumps(file_samples, indent=2)}"
        
        response = await self.gateway.generate_json(SCHEMA_RESOLVER_SYSTEM_PROMPT, user_prompt)
        
        tables = []
        for table_data in response.get("tables", []):
            tables.append(TableClassification(**table_data))
            
        return SchemaMapping(
            primary_entity_key=response["primary_entity_key"],
            tables=tables
        )
