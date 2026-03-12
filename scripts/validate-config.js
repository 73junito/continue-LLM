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

const configPath = process.argv[2] || path.join(__dirname, '..', 'config.yaml');
const schemaPath = path.join(__dirname, '..', 'config.schema.json');

try {
  const config = loadYaml(configPath);
  const schema = loadJson(schemaPath);
  const validate = ajv.compile(schema);
  const valid = validate(config);

  if (valid) {
    console.log('config.yaml is valid according to config.schema.json');
    process.exit(0);
  } else {
    console.error('Validation errors:\n' + ajv.errorsText(validate.errors, { separator: '\n' }));
    process.exit(2);
  }
} catch (err) {
  console.error('Failed to validate config:', err.message || err);
  process.exit(3);
}
