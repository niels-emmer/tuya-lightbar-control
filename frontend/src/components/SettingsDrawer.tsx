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
} from "@mantine/core";
import { IconCheck, IconInfoCircle } from "@tabler/icons-react";
import { api, type AppSettings } from "../api";

interface Props {
  opened: boolean;
  onClose: () => void;
}

const DEFAULT: AppSettings = {
  brightness: 80,
  auto_on: null,
  auto_off: null,
  weather_lat: 52.92,
  weather_lon: 6.43,
};

export function SettingsDrawer({ opened, onClose }: Props) {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
