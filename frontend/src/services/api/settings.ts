import api from "@/lib/api";

export interface AppSettings {
  ai_provider: "openrouter" | "anthropic" | "off";
  ai_model: string;
  parse_threshold: number;
  // расширяется по мере добавления полей в backend
  [key: string]: unknown;
}

export const settingsApi = {
  async get(): Promise<AppSettings> {
    const { data } = await api.get<AppSettings>("/settings");
    return data;
  },
  async update(input: Partial<AppSettings>): Promise<AppSettings> {
    const { data } = await api.put<AppSettings>("/settings", input);
    return data;
  },
};
