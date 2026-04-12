import { useEffect, useState, useCallback } from "react";
import {
  AppShell,
  Container,
  Stack,
  Group,
  ActionIcon,
  Tooltip,
  Text,
  Center,
  Loader,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconSettings } from "@tabler/icons-react";
import { api, type DeviceStatus, type EffectDef, type EffectState } from "./api";
import { StatusBar } from "./components/StatusBar";
import { EffectPanel } from "./components/EffectPanel";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { ImportExport } from "./components/ImportExport";

export default function App() {
  const [status, setStatus] = useState<DeviceStatus | null>(null);
  const [backendReady, setBackendReady] = useState(false);
  const [effects, setEffects] = useState<EffectDef[]>([]);
  const [currentEffect, setCurrentEffect] = useState<EffectState | null>(null);
  const [loading, setLoading] = useState(true);
  const [settingsOpened, { open: openSettings, close: closeSettings }] = useDisclosure(false);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
      setBackendReady(true);
    } catch {
      setBackendReady(false);
      setStatus(null);
    }
  }, []);

  const fetchEffect = useCallback(async () => {
    try {
      const e = await api.getCurrentEffect();
      setCurrentEffect(e);
    } catch {
      setCurrentEffect(null);
    }
  }, []);

  // Initial load
  useEffect(() => {
    Promise.all([
      api.getEffects().then(setEffects).catch(() => {}),
      fetchStatus(),
      fetchEffect(),
    ]).finally(() => setLoading(false));
  }, [fetchStatus, fetchEffect]);

  // Poll status every 5 s
  useEffect(() => {
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const handlePowerToggle = async () => {
    if (!status) return;
    await api.setPower(!status.power).catch(() => {});
    await fetchStatus();
  };

  const handleEffectChange = () => {
    fetchEffect();
  };

  if (loading) {
    return (
      <Center h="100vh">
        <Loader color="brand" />
      </Center>
    );
  }

  return (
    <>
      <AppShell header={{ height: 44 }}>
        <AppShell.Header>
          <StatusBar
            status={status}
            backendReady={backendReady}
            onPowerToggle={handlePowerToggle}
            onRefresh={fetchStatus}
          />
        </AppShell.Header>

        <AppShell.Main>
          <Container size="sm" py="md">
            <Stack gap="md">
              {effects.length > 0 ? (
                <EffectPanel
                  effects={effects}
                  currentEffect={currentEffect}
                  onEffectChange={handleEffectChange}
                  deviceOnline={status?.online ?? false}
                />
              ) : (
                <Text c="dimmed" ta="center">
                  Could not load effects — is the backend running?
                </Text>
              )}

              <Group justify="space-between" px={4}>
                <ImportExport
                  currentEffect={currentEffect}
                  effects={effects}
                  onImport={handleEffectChange}
                />
                <Tooltip label="Settings">
                  <ActionIcon variant="subtle" color="gray" onClick={openSettings}>
                    <IconSettings size={18} />
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Stack>
          </Container>
        </AppShell.Main>
      </AppShell>

      <SettingsDrawer opened={settingsOpened} onClose={closeSettings} />
    </>
  );
}
