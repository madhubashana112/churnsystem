from typing import Dict
from churn_platform.domain.interfaces.i_schema_resolver import ISchemaResolver
from churn_platform.domain.models.schema_mapping import SchemaMapping

class ResolveMultiSheetSchemaUseCase:
    def __init__(self, resolver: ISchemaResolver):
        self.resolver = resolver

    async def execute(self, file_samples: Dict[str, str]) -> SchemaMapping:
        return await self.resolver.resolve(file_samples)
