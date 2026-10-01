import {JsonSchema} from '../../../models/workflow';

export function formatWorkflowKey(value: string): string {
  return value.replace(/[._-]+/g, ' ').replace(/\b\w/g, character => character.toUpperCase());
}

export function exampleInput(schema: JsonSchema): Record<string, unknown> {
  const value = exampleValue(schema);
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}

function exampleValue(schema: JsonSchema): unknown {
  if (schema.default !== undefined) return schema.default;
  if (schema.enum?.length) return schema.enum[0];
  const type = Array.isArray(schema.type) ? schema.type[0] : schema.type;
  if (type === 'object') {
    return Object.fromEntries(Object.entries(schema.properties ?? {})
      .filter(([name, property]) => schema.required?.includes(name) || property.default !== undefined)
      .map(([name, property]) => [name, exampleValue(property)]));
  }
  if (type === 'array') return [];
  if (type === 'boolean') return false;
  if (type === 'integer' || type === 'number') return 0;
  if (type === 'string') return '';
  if (type === 'null') return null;
  return {};
}

function valueType(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  if (typeof value === 'number') return Number.isInteger(value) ? 'integer' : 'number';
  return typeof value === 'object' ? 'object' : typeof value;
}

export function validateInput(value: unknown, schema: JsonSchema, path = 'input'): string | null {
  const types = Array.isArray(schema.type) ? schema.type : schema.type ? [schema.type] : [];
  const actual = valueType(value);
  if (types.length && !types.some(type => type === actual || (type === 'number' && actual === 'integer'))) {
    return `${path} must be ${types.join(' or ')}.`;
  }
  if (schema.enum && !schema.enum.some(item => JSON.stringify(item) === JSON.stringify(value))) {
    return `${path} must be one of ${schema.enum.map(item => JSON.stringify(item)).join(', ')}.`;
  }
  if (typeof value === 'string') {
    if (typeof schema['minLength'] === 'number' && value.length < schema['minLength']) return `${path} is too short.`;
    if (typeof schema['maxLength'] === 'number' && value.length > schema['maxLength']) return `${path} is too long.`;
  }
  if (typeof value === 'number') {
    if (typeof schema['minimum'] === 'number' && value < schema['minimum']) return `${path} is too small.`;
    if (typeof schema['maximum'] === 'number' && value > schema['maximum']) return `${path} is too large.`;
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const object = value as Record<string, unknown>;
    for (const name of schema.required ?? []) if (!(name in object)) return `${path}.${name} is required.`;
    if (schema.additionalProperties === false) {
      const unknown = Object.keys(object).filter(name => !(name in (schema.properties ?? {})));
      if (unknown.length) return `${path} has unknown properties: ${unknown.join(', ')}.`;
    }
    for (const [name, child] of Object.entries(schema.properties ?? {})) {
      if (name in object) { const error = validateInput(object[name], child, `${path}.${name}`); if (error) return error; }
    }
  } else if (Array.isArray(value) && schema.items) {
    for (let index = 0; index < value.length; index++) {
      const error = validateInput(value[index], schema.items, `${path}[${index}]`); if (error) return error;
    }
  }
  return null;
}
