import { useParams } from "react-router-dom";
import { PageHeader } from "@/components/ui-domain/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/ui-domain/EmptyState";

export default function SupplierPage() {
  const { slug } = useParams<{ slug: string }>();
  const name = slug ? decodeURIComponent(slug) : "Поставщик";

  return (
    <div className="container-page py-8">
      <PageHeader serif title={name} subtitle="Профиль поставщика" />
      <Tabs defaultValue="overview" className="mt-6">
        <TabsList>
          <TabsTrigger value="overview">Обзор</TabsTrigger>
          <TabsTrigger value="invoices">Счета</TabsTrigger>
          <TabsTrigger value="projects">Объекты</TabsTrigger>
          <TabsTrigger value="compare">Сравнение</TabsTrigger>
        </TabsList>
        {(["overview", "invoices", "projects", "compare"] as const).map((tab) => (
          <TabsContent key={tab} value={tab} className="pt-6">
            <EmptyState
              title="Подробная аналитика по поставщику"
              description="Будет доступна после обновления сервиса."
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
