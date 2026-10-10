import { useEffect, useState, useCallback } from "react";
import {
  AppShell,
  Container,
  Stack,
  Center,
  Loader,
  Text,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { api, ApiError, type DeviceStatus, type EffectDef, type EffectState } from "./api";
import { TopBar } from "./components/TopBar";
import { StatusCard } from "./components/StatusCard";
import { EffectCard } from "./components/EffectCard";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { ApiKeyModal } from "./components/ApiKeyModal";
import { Footer } from "./components/Footer";

const OVERRIDES_KEY = "lightbar-param-overrides";

function loadOverrides(): Record<string, Record<string, unknown>> {
  try { return JSON.parse(localStorage.getItem(OVERRIDES_KEY) ?? "{}"); }
  catch { return {}; }
}
function saveOverrides(o: Record<string, Record<string, unknown>>) {
  localStorage.setItem(OVERRIDES_KEY, JSON.stringify(o));
}

export default function App() {
  const [status, setStatus] = useState<DeviceStatus | null>(null);
  const [backendReady, setBackendReady] = useState(false);
  const [effects, setEffects] = useState<EffectDef[]>([]);
  const [currentEffect, setCurrentEffect] = useState<EffectState | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedEffect, setSelectedEffect] = useState<string | null>(null);
  const [paramOverrides, setParamOverrides] = useState<Record<string, Record<string, unknown>>>(loadOverrides);
  const [settingsOpened, { open: openSettings, close: closeSettings }] = useDisclosure(false);
  const [authRequired, setAuthRequired] = useState(false);

  const handleAuthError = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) setAuthRequired(true);
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
      setBackendReady(true);
    } catch (e) {
      handleAuthError(e);
      setBackendReady(false);
      setStatus(null);
    }
  }, [handleAuthError]);

  const fetchEffect = useCallback(async () => {
    try {
      setCurrentEffect(await api.getCurrentEffect());
    } catch (e) {
      handleAuthError(e);
      setCurrentEffect(null);
    }
  }, [handleAuthError]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      api.getEffects()
        .then((list) => {
          setEffects(list);
          // Default selection: first effect
          setSelectedEffect((prev) => prev ?? list[0]?.name ?? null);
        })
        .catch(handleAuthError),
      fetchStatus(),
      fetchEffect(),
    ]);
    setLoading(false);
  }, [fetchStatus, fetchEffect, handleAuthError]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const handleStop = async () => {
    await api.stopEffect().catch(() => {});
    await fetchEffect();
  };

  const handleImport = async (name: string, params: Record<string, unknown>) => {
    try {
      await api.activateEffect(name, params);
      const nextOverrides = { ...paramOverrides, [name]: params };
      setParamOverrides(nextOverrides);
      saveOverrides(nextOverrides);
      setSelectedEffect(name);
      await fetchEffect();
    } catch {
      alert("Failed to activate imported effect.");
    }
  };

  const handleKeySaved = () => {
    setAuthRequired(false);
    void loadAll();
  };

  const selectedEffectDef = effects.find((e) => e.name === selectedEffect) ?? null;

  if (loading) {
    return (
      <Center h="100vh">
        <Loader color="brand" />
      </Center>
    );
  }

  return (
    <>
      <AppShell header={{ height: 48 }} footer={{ height: "auto" }}>
        <AppShell.Header>
          <TopBar
            activeEffect={currentEffect}
            onStop={handleStop}
            onSettingsOpen={openSettings}
          />
        </AppShell.Header>

        <AppShell.Main>
          <Container size="sm" py="md">
            <Stack gap="md">
              <StatusCard
                status={status}
                backendReady={backendReady}
                effects={effects}
                activeEffect={currentEffect}
                selectedEffect={selectedEffect}
                onSelectEffect={setSelectedEffect}
                onImport={handleImport}
              />

              {effects.length === 0 ? (
                <Text c="dimmed" ta="center" size="sm">
                  Could not load effects — is the backend running?
                </Text>
              ) : selectedEffectDef ? (
                <EffectCard
                  key={selectedEffect}
                  effect={selectedEffectDef}
                  activeEffect={currentEffect}
                  onEffectChange={fetchEffect}
                  paramOverride={paramOverrides[selectedEffect!]}
                />
              ) : null}
            </Stack>
          </Container>
        </AppShell.Main>

        <AppShell.Footer>
          <Footer />
        </AppShell.Footer>
      </AppShell>

      <SettingsDrawer opened={settingsOpened} onClose={closeSettings} />
      <ApiKeyModal opened={authRequired} onSaved={handleKeySaved} />
    </>
  );
}
