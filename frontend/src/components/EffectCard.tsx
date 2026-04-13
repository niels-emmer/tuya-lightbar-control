import { useState, useEffect } from "react";
import {
  Card, Title, Badge, Text, Stack, Group, Button, Collapse, Code, Anchor, Alert,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconCode, IconInfoCircle } from "@tabler/icons-react";
import { ParamField } from "./ParamField";
import { api } from "../api";
import type { EffectDef, EffectState } from "../api";

interface Props {
  effect: EffectDef;
  activeEffect: EffectState | null;
  onEffectChange: () => void;
  paramOverride?: Record<string, unknown>;
}

function buildDefaults(effect: EffectDef): Record<string, unknown> {
  return Object.fromEntries(effect.params.map((p) => [p.key, p.default ?? ""]));
}

export function EffectCard({ effect, activeEffect, onEffectChange, paramOverride }: Props) {
  const [params, setParams] = useState<Record<string, unknown>>(() => buildDefaults(effect));
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiOpen, { toggle: toggleApi }] = useDisclosure(false);

  // Re-initialise when a JSON import provides new param values
  useEffect(() => {
    if (paramOverride && Object.keys(paramOverride).length > 0) {
      setParams({ ...buildDefaults(effect), ...paramOverride });
    }
  }, [paramOverride]); // paramOverride ref changes only on import

  const isActive = activeEffect?.name === effect.name;

  const setParam = (key: string, val: unknown) =>
    setParams((p) => ({ ...p, [key]: val }));

  const handleActivate = async () => {
    setActivating(true);
    setError(null);
    try {
      await api.activateEffect(effect.name, params);
      onEffectChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to activate");
    } finally {
      setActivating(false);
    }
  };

  const handleStop = async () => {
    try {
      await api.stopEffect();
      onEffectChange();
    } catch {
      // ignore
    }
  };

  const apiSample = JSON.stringify({ name: effect.name, params }, null, 2);

  return (
    <Card id={effect.name} withBorder radius="md" p="md">
      <Stack gap="sm">
        {/* Header */}
        <Group justify="space-between" wrap="nowrap">
          <Title order={4}>{effect.label}</Title>
          {isActive && (
            <Badge color="green" variant="light" style={{ flexShrink: 0 }}>
              Active
            </Badge>
          )}
        </Group>

        {effect.description && (
          <Text size="sm" c="dimmed">{effect.description}</Text>
        )}

        {/* Params */}
        {effect.params.length > 0 && (
          <Stack gap="xs">
            {effect.params.map((p) => (
              <ParamField
                key={p.key}
                schema={p}
                value={params[p.key]}
                onChange={(v) => setParam(p.key, v)}
              />
            ))}
          </Stack>
        )}

        {error && (
          <Alert color="red" icon={<IconInfoCircle size={16} />} py="xs">
            {error}
          </Alert>
        )}

        {/* Actions */}
        <Group gap="xs">
          <Button size="sm" onClick={handleActivate} loading={activating}>
            Activate
          </Button>
          <Button size="sm" variant="subtle" color="gray" onClick={handleStop}>
            Stop
          </Button>
          <Button
            size="sm"
            variant="subtle"
            color="gray"
            leftSection={<IconCode size={14} />}
            onClick={toggleApi}
            ml="auto"
          >
            {apiOpen ? "Hide API call" : "Show API call"}
          </Button>
        </Group>

        {/* Collapsible API sample */}
        <Collapse in={apiOpen}>
          <Stack gap={6}>
            <Group justify="space-between">
              <Text size="xs" c="dimmed" fw={500}>POST /api/effect</Text>
              <Anchor
                href="http://localhost:8000/docs#/effects/activate_effect_api_effect_post"
                target="_blank"
                size="xs"
              >
                API reference ↗
              </Anchor>
            </Group>
            <Code block style={{ fontSize: 12 }}>{apiSample}</Code>
          </Stack>
        </Collapse>
      </Stack>
    </Card>
  );
}
