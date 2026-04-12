import { useState, useEffect } from "react";
import {
  Paper,
  Select,
  Text,
  Button,
  Group,
  Stack,
  Badge,
  Alert,
  Divider,
} from "@mantine/core";
import { IconPlayerPlay, IconPlayerStop, IconInfoCircle } from "@tabler/icons-react";
import type { EffectDef, EffectState } from "../api";
import { api } from "../api";
import { ParamField } from "./ParamField";

interface Props {
  effects: EffectDef[];
  currentEffect: EffectState | null;
  onEffectChange: () => void;
  deviceOnline: boolean;
}

export function EffectPanel({ effects, currentEffect, onEffectChange, deviceOnline }: Props) {
  const [selectedName, setSelectedName] = useState<string>(effects[0]?.name ?? "");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedDef = effects.find((e) => e.name === selectedName);

  // Initialise params with defaults when effect selection changes
  useEffect(() => {
    if (!selectedDef) return;
    const defaults: Record<string, unknown> = {};
    for (const p of selectedDef.params) {
      defaults[p.key] = p.default;
    }
    setParams(defaults);
    setError(null);
  }, [selectedName, selectedDef]);

  const handleActivate = async () => {
    if (!selectedDef) return;
    setLoading(true);
    setError(null);
    try {
      await api.activateEffect(selectedName, params);
      onEffectChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to activate effect");
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await api.stopEffect();
      onEffectChange();
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper p="md">
      <Stack gap="md">
        <Group justify="space-between">
          <Text fw={600} size="lg">Effect</Text>
          {currentEffect && (
            <Badge color="green" variant="light">
              {effects.find((e) => e.name === currentEffect.name)?.label ?? currentEffect.name}
            </Badge>
          )}
        </Group>

        <Select
          label="Select effect"
          data={effects.map((e) => ({ value: e.name, label: e.label }))}
          value={selectedName}
          onChange={(v) => v && setSelectedName(v)}
        />

        {selectedDef?.description && (
          <Text size="sm" c="dimmed">{selectedDef.description}</Text>
        )}

        {selectedDef && selectedDef.params.length > 0 && (
          <>
            <Divider label="Parameters" labelPosition="left" />
            {selectedDef.params.map((p) => (
              <ParamField
                key={p.key}
                schema={p}
                value={params[p.key]}
                onChange={(v) => setParams((prev) => ({ ...prev, [p.key]: v }))}
              />
            ))}
          </>
        )}

        {error && (
          <Alert color="red" icon={<IconInfoCircle size={16} />}>
            {error}
          </Alert>
        )}

        <Group>
          <Button
            leftSection={<IconPlayerPlay size={16} />}
            onClick={handleActivate}
            loading={loading}
            disabled={!deviceOnline || !selectedDef}
            flex={1}
          >
            Activate
          </Button>
          <Button
            leftSection={<IconPlayerStop size={16} />}
            variant="light"
            color="red"
            onClick={handleStop}
            loading={loading}
            disabled={!currentEffect}
          >
            Stop
          </Button>
        </Group>
      </Stack>
    </Paper>
  );
}
