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
import { api, type DeviceStatus, type EffectDef, type EffectState } from "./api";
import { TopBar } from "./components/TopBar";
import { StatusCard } from "./components/StatusCard";
import { EffectCard } from "./components/EffectCard";
import { SettingsDrawer } from "./components/SettingsDrawer";

const HIDDEN_KEY = "lightbar-hidden-cards";
const OVERRIDES_KEY = "lightbar-param-overrides";

function loadHidden(): string[] {
  try { return JSON.parse(localStorage.getItem(HIDDEN_KEY) ?? "[]"); }
  catch { return []; }
}
function saveHidden(h: string[]) {
  localStorage.setItem(HIDDEN_KEY, JSON.stringify(h));
}
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
  const [hiddenCards, setHiddenCards] = useState<string[]>(loadHidden);
  const [paramOverrides, setParamOverrides] = useState<Record<string, Record<string, unknown>>>(loadOverrides);
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

  useEffect(() => {
    Promise.all([
      api.getEffects().then(setEffects).catch(() => {}),
      fetchStatus(),
      fetchEffect(),
    ]).finally(() => setLoading(false));
  }, [fetchStatus, fetchEffect]);

  useEffect(() => {
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const handleStop = async () => {
    await api.stopEffect().catch(() => {});
    await fetchEffect();
  };

  const handleRemoveCard = (name: string) => {
    const next = [...hiddenCards, name];
    setHiddenCards(next);
    saveHidden(next);
  };

  const handleRestoreCard = (name: string) => {
    const next = hiddenCards.filter((n) => n !== name);
    setHiddenCards(next);
    saveHidden(next);
  };

  const handleImport = async (name: string, params: Record<string, unknown>) => {
    try {
      await api.activateEffect(name, params);
      // Restore card if hidden
      if (hiddenCards.includes(name)) {
        handleRestoreCard(name);
      }
      // Store param override so the card pre-fills
      const nextOverrides = { ...paramOverrides, [name]: params };
      setParamOverrides(nextOverrides);
      saveOverrides(nextOverrides);
      await fetchEffect();
    } catch {
      alert("Failed to activate imported effect.");
    }
  };

  const visibleCards = effects.map((e) => e.name).filter((n) => !hiddenCards.includes(n));
  const hiddenCardNames = hiddenCards.filter((n) => effects.some((e) => e.name === n));

  if (loading) {
    return (
      <Center h="100vh">
        <Loader color="brand" />
      </Center>
    );
  }

  return (
    <>
      <AppShell header={{ height: 48 }}>
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
                visibleCards={visibleCards}
                hiddenCards={hiddenCardNames}
                onImport={handleImport}
                onRemoveCard={handleRemoveCard}
                onRestoreCard={handleRestoreCard}
              />

              {effects.length === 0 ? (
                <Text c="dimmed" ta="center" size="sm">
                  Could not load effects — is the backend running?
                </Text>
              ) : (
                visibleCards.map((name) => {
                  const effect = effects.find((e) => e.name === name);
                  if (!effect) return null;
                  return (
                    <EffectCard
                      key={name}
                      effect={effect}
                      activeEffect={currentEffect}
                      onEffectChange={fetchEffect}
                      paramOverride={paramOverrides[name]}
                    />
                  );
                })
              )}
            </Stack>
          </Container>
        </AppShell.Main>
      </AppShell>

      <SettingsDrawer opened={settingsOpened} onClose={closeSettings} />
    </>
  );
}
