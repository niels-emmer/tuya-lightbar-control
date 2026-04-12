import { Group, Indicator, Text, ActionIcon, Tooltip } from "@mantine/core";
import { IconBulb, IconBulbOff, IconRefresh } from "@tabler/icons-react";
import type { DeviceStatus } from "../api";

interface Props {
  status: DeviceStatus | null;
  backendReady: boolean;
  onPowerToggle: () => void;
  onRefresh: () => void;
}

export function StatusBar({ status, backendReady, onPowerToggle, onRefresh }: Props) {
  const deviceOnline = status?.online ?? false;
  const powered = status?.power ?? false;

  return (
    <Group justify="space-between" px="md" py="xs" style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
      <Group gap="xl">
        <Group gap="xs">
          <Indicator color={backendReady ? "green" : "red"} size={10} processing={!backendReady}>
            <Text size="sm" c={backendReady ? "dimmed" : "red"}>Backend</Text>
          </Indicator>
        </Group>
        <Group gap="xs">
          <Indicator color={deviceOnline ? "green" : "gray"} size={10} processing={deviceOnline}>
            <Text size="sm" c={deviceOnline ? "dimmed" : "dimmed"}>
              Device {deviceOnline ? (powered ? "on" : "standby") : "offline"}
            </Text>
          </Indicator>
        </Group>
      </Group>

      <Group gap="xs">
        <Tooltip label="Refresh status">
          <ActionIcon variant="subtle" color="gray" onClick={onRefresh}>
            <IconRefresh size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label={powered ? "Turn off" : "Turn on"}>
          <ActionIcon
            variant="subtle"
            color={powered ? "yellow" : "gray"}
            onClick={onPowerToggle}
            disabled={!deviceOnline}
          >
            {powered ? <IconBulb size={18} /> : <IconBulbOff size={18} />}
          </ActionIcon>
        </Tooltip>
      </Group>
    </Group>
  );
}
