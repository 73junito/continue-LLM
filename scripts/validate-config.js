const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const Ajv = require('ajv');

const ajv = new Ajv({ allErrors: true, strict: false });

function loadYaml(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  return yaml.load(raw);
}

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

const defaultConfig = path.join(__dirname, '..', 'config.yaml');
const schemaPath = path.join(__dirname, '..', 'config.schema.json');

const files = process.argv.slice(2).length ? process.argv.slice(2) : [defaultConfig];

try {
  const schema = loadJson(schemaPath);
  const validate = ajv.compile(schema);

  for (const filePath of files) {
    try {
      console.log(`Validating ${filePath}...`);
      const config = loadYaml(filePath);
      const valid = validate(config);

      if (!valid) {
        console.error(`❌ ${filePath} is invalid`);
        console.error(ajv.errorsText(validate.errors, { separator: '\n' }));
        process.exit(2);
      }

      console.log(`✅ ${filePath} is valid`);
    } catch (err) {
      console.error(`Failed to validate ${filePath}:`, err.message || err);
      process.exit(3);
    }
  }

  process.exit(0);
} catch (err) {
  console.error('Failed to load schema or initialize validator:', err.message || err);
  process.exit(3);
}
