import { Group, Text, Anchor } from "@mantine/core";

const VERSION = "dev";
const GITHUB_URL = "https://github.com/niels-emmer/tuya-lightbar-control";

export function Footer() {
  return (
    <Group
      justify="center"
      gap="md"
      py="xs"
      px="md"
      style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}
    >
      <Anchor href="docs/" target="_blank" size="xs" c="dimmed">
        API docs ↗
      </Anchor>
      <Text size="xs" c="dimmed">·</Text>
      <Anchor href={GITHUB_URL} target="_blank" size="xs" c="dimmed">
        GitHub ↗
      </Anchor>
      <Text size="xs" c="dimmed">·</Text>
      <Text size="xs" c="dimmed">{VERSION}</Text>
    </Group>
  );
}
