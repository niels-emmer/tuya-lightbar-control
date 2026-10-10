import { useState } from "react";
import { Modal, TextInput, Button, Text, Stack } from "@mantine/core";
import { setApiKey } from "../auth";

interface Props {
  opened: boolean;
  onSaved: () => void;
}

/**
 * Shown when the API returns 401 — the deployment has API_KEY set but this
 * browser has not stored it yet.
 */
export function ApiKeyModal({ opened, onSaved }: Props) {
  const [value, setValue] = useState("");

  return (
    <Modal
      opened={opened}
      onClose={() => {}}
      title="API key required"
      centered
      withCloseButton={false}
    >
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          This lightbar API requires an API key. Enter it to continue — it is
          stored in this browser only and never sent anywhere else.
        </Text>
        <TextInput
          label="API key"
          placeholder="the API_KEY value from .env"
          type="password"
          value={value}
          onChange={(e) => setValue(e.currentTarget.value)}
          data-autofocus
        />
        <Button
          disabled={!value.trim()}
          onClick={() => {
            setApiKey(value.trim());
            onSaved();
          }}
        >
          Save &amp; retry
        </Button>
      </Stack>
    </Modal>
  );
}
