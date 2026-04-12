import { useRef } from "react";
import { Group, Button, Tooltip } from "@mantine/core";
import { IconDownload, IconUpload } from "@tabler/icons-react";
import type { EffectState, EffectDef } from "../api";
import { api } from "../api";

interface Props {
  currentEffect: EffectState | null;
  effects: EffectDef[];
  onImport: () => void;
}

export function ImportExport({ currentEffect, effects, onImport }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);

  const handleExport = () => {
    if (!currentEffect) return;
    const def = effects.find((e) => e.name === currentEffect.name);
    const payload = {
      name: currentEffect.name,
      label: def?.label ?? currentEffect.name,
      params: currentEffect.params,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lightbar-${currentEffect.name}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
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
        await api.activateEffect(data.name, data.params ?? {});
        onImport();
      } catch {
        alert("Failed to import effect. Check the file format.");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  return (
    <Group gap="xs">
      <input
        ref={fileRef}
        type="file"
        accept=".json"
        style={{ display: "none" }}
        onChange={handleImport}
      />
      <Tooltip label="Import effect from JSON">
        <Button
          size="xs"
          variant="subtle"
          leftSection={<IconUpload size={14} />}
          onClick={() => fileRef.current?.click()}
        >
          Import
        </Button>
      </Tooltip>
      <Tooltip label={currentEffect ? "Export current effect to JSON" : "No active effect to export"}>
        <Button
          size="xs"
          variant="subtle"
          leftSection={<IconDownload size={14} />}
          onClick={handleExport}
          disabled={!currentEffect}
        >
          Export
        </Button>
      </Tooltip>
    </Group>
  );
}
