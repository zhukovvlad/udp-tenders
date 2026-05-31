import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Building, Info } from "lucide-react";
import { toast } from "sonner";

import { Surface } from "@/components/ui-domain/Surface";
import { Button } from "@/components/ui-domain/Button";
import { Skeleton } from "@/components/ui-domain/Skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PasswordField } from "@/components/admin/PasswordField";
import { OrgRoleBadge } from "@/components/admin/RoleBadges";
import { useAdminOrganization, useCreateAdminUser } from "@/services/queries";
import { generatePassword } from "@/lib/password";
import { cn } from "@/lib/utils";
import type { OrgRole } from "@/types/auth";

const ROLES: OrgRole[] = ["superadmin", "admin", "member"];

export default function AdminUserCreate() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const orgId = Number(id);

  const orgQ = useAdminOrganization(orgId);
  const createUser = useCreateAdminUser();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState(() => generatePassword());
  const [role, setRole] = useState<OrgRole>("member");
  const [isActive, setIsActive] = useState(true);

  const isEmptyOrg = orgQ.data ? orgQ.data.users.length === 0 : false;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await createUser.mutateAsync({
        orgId,
        input: { email, password, org_role: role, is_active: isActive },
      });
      toast.success("Пользователь создан — передайте пароль безопасным способом");
      navigate(`/admin/organizations/${orgId}`);
    } catch {
      // тосты в onError
    }
  }

  return (
    <div className="container-page py-8">
      <div className="mx-auto max-w-xl">
        <button
          type="button"
          onClick={() => navigate(`/admin/organizations/${orgId}`)}
          className="mb-4 flex items-center gap-2 text-sm text-fg-secondary hover:text-fg"
        >
          <ArrowLeft size={18} />
          Новый пользователь
        </button>

        <form onSubmit={handleSubmit}>
          <Surface padding="lg" className="flex flex-col gap-4">
            {/* Организация — предзаполнена и заблокирована (переход из карточки) */}
            <div className="flex flex-col gap-1.5">
              <Label>Организация</Label>
              {orgQ.isPending ? (
                <Skeleton className="h-10 w-full" />
              ) : (
                <div className="flex items-center gap-2 rounded-md border border-border-default px-3 py-2 text-sm text-fg">
                  <Building size={15} className="text-fg-secondary" />
                  {orgQ.data?.name ?? "—"}
                </div>
              )}
              <p className="text-xs text-fg-tertiary">Заполнено автоматически — переход со страницы организации.</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="user-email">Email</Label>
              <Input
                id="user-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="i.orlova@stroygrad.ru"
                required
                autoComplete="off"
              />
            </div>

            <PasswordField value={password} onChange={setPassword} />

            <div className="flex flex-col gap-1.5">
              <Label>Роль в организации</Label>
              <div className="grid grid-cols-3 gap-2">
                {ROLES.map((r) => {
                  const active = role === r;
                  return (
                    <button
                      key={r}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setRole(r)}
                      className={cn(
                        "flex items-center justify-center rounded-md border p-2 transition-colors",
                        active ? "border-accent bg-accent/10" : "border-border-default hover:bg-surface-hover",
                      )}
                    >
                      <OrgRoleBadge role={r} />
                    </button>
                  );
                })}
              </div>
              {isEmptyOrg && (
                <p className="flex items-center gap-1 text-xs text-fg-tertiary">
                  <Info size={13} />
                  Организация пуста — первый пользователь получит superadmin автоматически.
                </p>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-border-subtle pt-4">
              <div>
                <p className="text-sm text-fg">Активен</p>
                <p className="text-xs text-fg-secondary">Может входить в систему сразу после создания</p>
              </div>
              <Switch checked={isActive} onCheckedChange={setIsActive} />
            </div>
          </Surface>

          <div className="mt-4 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => navigate(`/admin/organizations/${orgId}`)}>
              Отмена
            </Button>
            <Button type="submit" loading={createUser.isPending} disabled={!email || !password}>
              Создать пользователя
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
