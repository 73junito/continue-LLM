const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const Ajv = require('ajv');

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function loadYaml(filePath) {
  return yaml.load(fs.readFileSync(filePath, 'utf8'));
}

const rootSchemaPath = path.join(__dirname, '..', 'config.schema.json');
const defsDir = path.join(__dirname, '..', 'schema', 'defs');
const providersDir = path.join(__dirname, '..', 'schema', 'providers');
const examplesDir = path.join(__dirname, '..', 'examples');

const ajv = new Ajv({ allErrors: true, strict: false });

try {
  // Preload defs and providers so $ref can resolve
  if (fs.existsSync(defsDir)) {
    for (const f of fs.readdirSync(defsDir)) {
      if (f.endsWith('.json')) {
        const p = path.join(defsDir, f);
        const s = loadJson(p);
        ajv.addSchema(s, p);
      }
    }
  }

  if (fs.existsSync(providersDir)) {
    for (const f of fs.readdirSync(providersDir)) {
      if (f.endsWith('.json')) {
        const p = path.join(providersDir, f);
        const s = loadJson(p);
        ajv.addSchema(s, p);
      }
    }
  }

  const root = loadJson(rootSchemaPath);
  const validate = ajv.compile(root);

  // Validate each example
  if (fs.existsSync(examplesDir)) {
    for (const f of fs.readdirSync(examplesDir)) {
      if (!f.endsWith('.yaml') && !f.endsWith('.yml')) continue;
      const p = path.join(examplesDir, f);
      console.log(`Validating ${p} against ${rootSchemaPath}...`);
      const cfg = loadYaml(p);
      const ok = validate(cfg);
      if (!ok) {
        console.error(`❌ ${p} is invalid:`);
        console.error(ajv.errorsText(validate.errors, { separator: '\n' }));
        process.exit(2);
      }
      console.log(`✅ ${p} is valid`);
    }
  }

  console.log('All schema lint checks passed');
  process.exit(0);
} catch (err) {
  console.error('Schema lint failed:', err && err.message ? err.message : err);
  process.exit(3);
}
