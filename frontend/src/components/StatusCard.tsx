import { useRef, useState } from "react";
import {
  Card, Text, Group, Badge, Anchor, Divider, Button, Select, Stack, Title,
} from "@mantine/core";
import { IconUpload, IconDownload } from "@tabler/icons-react";
import type { DeviceStatus, EffectDef, EffectState } from "../api";

interface Props {
  status: DeviceStatus | null;
  backendReady: boolean;
  effects: EffectDef[];
  activeEffect: EffectState | null;
  visibleCards: string[];
  hiddenCards: string[];
  onImport: (name: string, params: Record<string, unknown>) => void;
  onRemoveCard: (name: string) => void;
  onRestoreCard: (name: string) => void;
}

export function StatusCard({
  status,
  backendReady,
  effects,
  activeEffect,
  visibleCards,
  hiddenCards,
  onImport,
  onRemoveCard,
  onRestoreCard,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [cardToRemove, setCardToRemove] = useState<string | null>(null);

  const backendColor = backendReady ? "green" : "red";
  const backendLabel = backendReady ? "Backend online" : "Backend offline";

  const deviceColor = !status?.online ? "red" : status.power ? "green" : "yellow";
  const deviceLabel = !status?.online
    ? "Device offline"
    : status.power
    ? "Device on"
    : "Device standby";

  const activeLabel = activeEffect
    ? (effects.find((e) => e.name === activeEffect.name)?.label ?? activeEffect.name)
    : null;

  const handleExport = () => {
    if (!activeEffect) return;
    const def = effects.find((e) => e.name === activeEffect.name);
    const payload = {
      name: activeEffect.name,
      label: def?.label ?? activeEffect.name,
      params: activeEffect.params,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lightbar-${activeEffect.name}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        const data = JSON.parse(ev.target?.result as string);
        if (!data.name || typeof data.name !== "string") {
          alert("Invalid effect file: missing 'name' field.");
          return;
        }
        onImport(data.name, data.params ?? {});
      } catch {
        alert("Failed to import effect. Check the file format.");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const visibleEffects = effects.filter((e) => visibleCards.includes(e.name));
  const hiddenEffects = effects.filter((e) => hiddenCards.includes(e.name));

  return (
    <Card withBorder radius="md" p="md">
      <Stack gap="md">
        {/* Header */}
        <div>
          <Title order={4}>Status</Title>
          <Text size="sm" c="dimmed">Monitor and control your Battletron lightbar</Text>
        </div>

        {/* Health badges */}
        <Group gap="xs">
          <Badge color={backendColor} variant="light">{backendLabel}</Badge>
          <Badge color={deviceColor} variant="light">{deviceLabel}</Badge>
          {activeLabel && (
            <Badge color="blue" variant="light">Running: {activeLabel}</Badge>
          )}
        </Group>

        {/* Links */}
        <Group gap="md">
          <Anchor href="docs/" target="_blank" size="sm">
            API docs ↗
          </Anchor>
          {visibleEffects.map((e) => (
            <Anchor key={e.name} href={`#${e.name}`} size="sm">
              {e.label}
            </Anchor>
          ))}
        </Group>

        <Divider label="Effect cards" labelPosition="left" />

        {/* Import / Export */}
        <Group gap="xs">
          <input
            ref={fileRef}
            type="file"
            accept=".json"
            style={{ display: "none" }}
            onChange={handleImportFile}
          />
          <Button
            size="xs"
            variant="subtle"
            leftSection={<IconUpload size={14} />}
            onClick={() => fileRef.current?.click()}
          >
            Import
          </Button>
          <Button
            size="xs"
            variant="subtle"
            leftSection={<IconDownload size={14} />}
            onClick={handleExport}
            disabled={!activeEffect}
          >
            Export active
          </Button>
        </Group>

        {/* Hide a card */}
        {visibleEffects.length > 0 && (
          <Group gap="xs" align="flex-end">
            <Select
              placeholder="Select card to hide…"
              size="xs"
              data={visibleEffects.map((e) => ({ value: e.name, label: e.label }))}
              value={cardToRemove}
              onChange={setCardToRemove}
              style={{ flex: 1 }}
              clearable
            />
            <Button
              size="xs"
              color="orange"
              variant="light"
              disabled={!cardToRemove}
              onClick={() => {
                if (cardToRemove) {
                  onRemoveCard(cardToRemove);
                  setCardToRemove(null);
                }
              }}
            >
              Hide card
            </Button>
          </Group>
        )}

        {/* Restore hidden cards */}
        {hiddenEffects.length > 0 && (
          <div>
            <Text size="xs" c="dimmed" mb={6}>Hidden cards</Text>
            <Group gap="xs">
              {hiddenEffects.map((e) => (
                <Button
                  key={e.name}
                  size="xs"
                  variant="outline"
                  color="gray"
                  onClick={() => onRestoreCard(e.name)}
                >
                  + {e.label}
                </Button>
              ))}
            </Group>
          </div>
        )}
      </Stack>
    </Card>
  );
}
