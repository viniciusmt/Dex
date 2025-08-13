const fs = require('fs').promises;
const converter = require('api-spec-converter');

async function convert() {
  try {
    const data = await fs.readFile('openapi.json', 'utf8');
    const openapi = JSON.parse(data);

    const result = await converter.convert({
      from: 'openapi_3',
      to: 'swagger_2',
      source: openapi
    });

    const swagger = result.spec || result;

    // Remove property servers
    delete swagger.servers;

    // Replace anyOf [string, null] with type string
    function replaceAnyOf(obj) {
      if (Array.isArray(obj)) {
        obj.forEach(replaceAnyOf);
        return;
      }
      if (obj && typeof obj === 'object') {
        for (const key of Object.keys(obj)) {
          if (key === 'anyOf') {
            const schemas = obj[key];
            if (Array.isArray(schemas) && schemas.length === 2) {
              const types = schemas.map(s => s.type).sort();
              if (types[0] === 'null' && types[1] === 'string') {
                obj.type = 'string';
                delete obj.anyOf;
                continue;
              }
            }
            schemas.forEach(replaceAnyOf);
          } else {
            replaceAnyOf(obj[key]);
          }
        }
      }
    }

    replaceAnyOf(swagger);

    await fs.writeFile('swagger2.json', JSON.stringify(swagger, null, 2));
    console.log('swagger2.json gerado com sucesso!');
  } catch (err) {
    console.error('Falha na conversão:', err.message);
    process.exit(1);
  }
}

convert();
