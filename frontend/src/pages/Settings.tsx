import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import api from "@/lib/api";

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("anthropic/claude-sonnet-4.6");
  const [threshold, setThreshold] = useState([70]);
  const [apiKeySet, setApiKeySet] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/settings").then((res) => {
      setApiKeySet(res.data.api_key_set);
      setModel(res.data.model);
      setThreshold([res.data.confidence_threshold * 100]);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const payload: Record<string, string | number> = {};
    if (apiKey) payload.api_key = apiKey;
    payload.model = model;
    payload.confidence_threshold = threshold[0] / 100;

    await api.put("/settings", payload);
    if (apiKey) setApiKeySet(true);
    setApiKey("");
    setSaving(false);
  };

  return (
    <Card className="max-w-lg">
      <CardHeader><CardTitle>Настройки</CardTitle></CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label>API-ключ OpenRouter</Label>
          <Input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={apiKeySet ? "••••••••••• (установлен)" : "sk-or-v1-..."}
          />
          <div>
            {apiKeySet
              ? <Badge variant="default">Ключ установлен</Badge>
              : <Badge variant="destructive">Не установлен</Badge>
            }
          </div>
        </div>

        <div className="space-y-2">
          <Label>Модель (OpenRouter)</Label>
          <Select value={model} onValueChange={setModel}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="anthropic/claude-sonnet-4.6">Claude Sonnet 4.6 (рекомендуется)</SelectItem>
              <SelectItem value="anthropic/claude-sonnet-4">Claude Sonnet 4</SelectItem>
              <SelectItem value="anthropic/claude-haiku-4">Claude Haiku 4 (быстрый)</SelectItem>
              <SelectItem value="google/gemini-2.5-flash">Gemini 2.5 Flash (дешёвый)</SelectItem>
              <SelectItem value="openai/gpt-4o">GPT-4o</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Порог уверенности: {threshold[0]}%</Label>
          <Slider value={threshold} onValueChange={setThreshold} min={0} max={100} step={5} />
        </div>

        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Сохранение..." : "Сохранить"}
        </Button>
      </CardContent>
    </Card>
  );
}
