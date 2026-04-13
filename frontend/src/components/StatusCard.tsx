import { useRef } from "react";
import {
  Card, Text, Group, Badge, Button, SimpleGrid, Stack, Title, Divider,
} from "@mantine/core";
import { IconUpload, IconDownload } from "@tabler/icons-react";
import type { DeviceStatus, EffectDef, EffectState } from "../api";

interface Props {
  status: DeviceStatus | null;
  backendReady: boolean;
  effects: EffectDef[];
  activeEffect: EffectState | null;
  selectedEffect: string | null;
  onSelectEffect: (name: string) => void;
  onImport: (name: string, params: Record<string, unknown>) => void;
}

export function StatusCard({
  status,
  backendReady,
  effects,
  activeEffect,
  selectedEffect,
  onSelectEffect,
  onImport,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);

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

  return (
    <Card withBorder radius="md" p="md">
      <Stack gap="sm">
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

        <Divider label="Effects" labelPosition="left" />

        {/* Effect selector buttons */}
        {effects.length > 0 && (
          <SimpleGrid cols={{ base: 2, xs: 3 }} spacing="xs">
            {effects.map((e) => {
              const isSelected = e.name === selectedEffect;
              const isActive = e.name === activeEffect?.name;
              return (
                <Button
                  key={e.name}
                  size="xs"
                  variant={isSelected ? "filled" : "light"}
                  color={isActive ? "blue" : isSelected ? "gray" : "gray"}
                  onClick={() => onSelectEffect(e.name)}
                  styles={{ root: { fontWeight: isSelected ? 600 : 400 } }}
                >
                  {e.label}
                </Button>
              );
            })}
          </SimpleGrid>
        )}

        <Divider label="Presets" labelPosition="left" />

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
      </Stack>
    </Card>
  );
}
