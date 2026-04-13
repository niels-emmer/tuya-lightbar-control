import { Group, Text, ThemeIcon, Button, ActionIcon, Tooltip } from "@mantine/core";
import { IconBolt, IconPlayerStop, IconSettings } from "@tabler/icons-react";
import type { EffectState } from "../api";

interface Props {
  activeEffect: EffectState | null;
  onStop: () => void;
  onSettingsOpen: () => void;
}

export function TopBar({ activeEffect, onStop, onSettingsOpen }: Props) {
  return (
    <Group h="100%" px="md" justify="space-between">
      <Group gap="xs">
        <ThemeIcon color="brand" variant="light" size="md" radius="sm">
          <IconBolt size={16} />
        </ThemeIcon>
        <Text fw={700} size="sm">Tuya Lightbar Control</Text>
      </Group>

      <Group gap="xs">
        <Button
          size="xs"
          color="red"
          variant="light"
          leftSection={<IconPlayerStop size={14} />}
          onClick={onStop}
          disabled={!activeEffect}
        >
          Stop
        </Button>
        <Tooltip label="Settings">
          <ActionIcon variant="subtle" color="gray" onClick={onSettingsOpen}>
            <IconSettings size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Group>
  );
}
