import {
  TextInput,
  NumberInput,
  Select,
  Slider,
  Text,
  Stack,
} from "@mantine/core";
import type { ParamSchema } from "../api";

interface Props {
  schema: ParamSchema;
  value: unknown;
  onChange: (val: unknown) => void;
}

export function ParamField({ schema, value, onChange }: Props) {
  const label = (
    <Text size="sm" fw={500}>
      {schema.label}
      {schema.unit ? <Text span c="dimmed" size="xs"> ({schema.unit})</Text> : null}
    </Text>
  );

  if (schema.type === "select") {
    return (
      <Select
        label={label}
        data={(schema.options ?? []).map((o) => ({
          value: String(o.value),
          label: o.label,
        }))}
        value={value !== undefined ? String(value) : String(schema.default ?? "")}
        onChange={(v) => {
          if (v == null) return;
          // Try to preserve numeric type if original options use numbers
          const opt = schema.options?.find((o) => String(o.value) === v);
          onChange(opt ? opt.value : v);
        }}
      />
    );
  }

  if (schema.type === "slider") {
    const numVal = typeof value === "number" ? value : Number(schema.default ?? 0);
    return (
      <Stack gap={4}>
        {label}
        <Slider
          value={numVal}
          onChange={onChange}
          min={schema.min ?? 0}
          max={schema.max ?? 100}
          step={schema.step ?? 1}
          marks={[
            { value: schema.min ?? 0, label: String(schema.min ?? 0) },
            { value: schema.max ?? 100, label: String(schema.max ?? 100) },
          ]}
          mb="xs"
        />
      </Stack>
    );
  }

  if (schema.type === "number") {
    return (
      <NumberInput
        label={label}
        value={typeof value === "number" ? value : Number(schema.default ?? 0)}
        onChange={(v) => onChange(v)}
        min={schema.min}
        max={schema.max}
        step={schema.step ?? 1}
        placeholder={schema.placeholder}
      />
    );
  }

  // text
  return (
    <TextInput
      label={label}
      value={typeof value === "string" ? value : String(schema.default ?? "")}
      onChange={(e) => onChange(e.currentTarget.value)}
      placeholder={schema.placeholder}
    />
  );
}
