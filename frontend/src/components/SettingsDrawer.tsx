import { useEffect, useState } from "react";
import {
  Drawer,
  Stack,
  Slider,
  TextInput,
  Text,
  Button,
  Group,
  Divider,
  NumberInput,
  Alert,
  Switch,
} from "@mantine/core";
import { useMantineColorScheme, useComputedColorScheme } from "@mantine/core";
import { IconCheck, IconInfoCircle } from "@tabler/icons-react";
import { api, type AppSettings } from "../api";
import { getApiKey, setApiKey as persistApiKey } from "../auth";

interface Props {
  opened: boolean;
  onClose: () => void;
}

const DEFAULT: AppSettings = {
  brightness: 80,
  auto_on: null,
  auto_off: null,
  weather_lat: 52.37,
  weather_lon: 4.89,
};

export function SettingsDrawer({ opened, onClose }: Props) {
  const { setColorScheme } = useMantineColorScheme();
  const computedScheme = useComputedColorScheme("dark");

  const [settings, setSettings] = useState<AppSettings>(DEFAULT);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiKeyDraft, setApiKeyDraft] = useState(getApiKey());
  const [keySaved, setKeySaved] = useState(false);

  useEffect(() => {
    if (opened) {
      api.getSettings().then(setSettings).catch(() => {});
    }
  }, [opened]);

  const set = <K extends keyof AppSettings>(key: K, val: AppSettings[K]) =>
    setSettings((s) => ({ ...s, [key]: val }));

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.saveSettings(settings);
      setSettings(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      title="Settings"
      position="right"
      size="sm"
    >
      <Stack gap="md">
        <Switch
          label="Dark mode"
          checked={computedScheme === "dark"}
          onChange={() =>
            setColorScheme(computedScheme === "dark" ? "light" : "dark")
          }
        />

        <Divider />

        <div>
          <Text size="sm" fw={500} mb={6}>Brightness</Text>
          <Slider
            value={settings.brightness}
            onChange={(v) => set("brightness", v)}
            min={5}
            max={100}
            step={5}
            marks={[
              { value: 5, label: "5%" },
              { value: 50, label: "50%" },
              { value: 100, label: "100%" },
            ]}
            mb="xs"
          />
        </div>

        <Divider label="Auto on/off" labelPosition="left" />
        <Group grow>
          <TextInput
            label="Turn on at"
            placeholder="HH:MM"
            value={settings.auto_on ?? ""}
            onChange={(e) => set("auto_on", e.currentTarget.value || null)}
          />
          <TextInput
            label="Turn off at"
            placeholder="HH:MM"
            value={settings.auto_off ?? ""}
            onChange={(e) => set("auto_off", e.currentTarget.value || null)}
          />
        </Group>

        <Divider label="Weather location (rain effect)" labelPosition="left" />
        <Group grow>
          <NumberInput
            label="Latitude"
            value={settings.weather_lat}
            onChange={(v) => set("weather_lat", Number(v))}
            decimalScale={4}
            step={0.01}
          />
          <NumberInput
            label="Longitude"
            value={settings.weather_lon}
            onChange={(v) => set("weather_lon", Number(v))}
            decimalScale={4}
            step={0.01}
          />
        </Group>

        <Divider label="API key (this browser)" labelPosition="left" />
        <TextInput
          label="API key"
          placeholder="leave empty if the API is open"
          type="password"
          value={apiKeyDraft}
          onChange={(e) => setApiKeyDraft(e.currentTarget.value)}
          description="Stored in this browser only; sent as X-API-Key. Reload after changing."
        />
        <Button
          size="xs"
          variant="light"
          color={keySaved ? "green" : "brand"}
          leftSection={keySaved ? <IconCheck size={14} /> : undefined}
          onClick={() => {
            persistApiKey(apiKeyDraft.trim());
            setKeySaved(true);
            setTimeout(() => setKeySaved(false), 2000);
          }}
        >
          {keySaved ? "Saved" : "Save API key"}
        </Button>

        {error && (
          <Alert color="red" icon={<IconInfoCircle size={16} />}>{error}</Alert>
        )}

        <Button
          leftSection={saved ? <IconCheck size={16} /> : undefined}
          color={saved ? "green" : "brand"}
          onClick={handleSave}
          loading={saving}
        >
          {saved ? "Saved" : "Save settings"}
        </Button>
      </Stack>
    </Drawer>
  );
}
