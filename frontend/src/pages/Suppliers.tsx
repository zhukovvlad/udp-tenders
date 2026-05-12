import { PageHeader } from "@/components/ui-domain/PageHeader";
import { EmptyState } from "@/components/ui-domain/EmptyState";

export default function Suppliers() {
  return (
    <div className="container-page py-8">
      <PageHeader serif title="Поставщики" subtitle="Компании, с которыми работает портфель" />
      <div className="mt-8">
        <EmptyState
          title="Аналитика по поставщикам"
          description="Для отображения реестра поставщиков требуется обновление сервиса. Данные по поставщикам доступны внутри карточки каждого объекта."
        />
      </div>
    </div>
  );
}
