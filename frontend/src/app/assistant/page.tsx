import { redirect } from "next/navigation";

export default function AssistantPage() {
  redirect("/?ask=1");
}
