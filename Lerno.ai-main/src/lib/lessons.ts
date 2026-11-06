import { supabase } from "./supabase";
import { mediaUrl, type Scene } from "./api";

export type Lesson = {
  id: string;
  prompt: string;
  title: string;
  scenes: Scene[];
  notes: string;
  lang: string;
  created_at: string;
  updated_at: string;
};
export type LessonSummary = Pick<Lesson, "id" | "title" | "prompt" | "created_at">;

export const LESSONS_EVENT = "lerno:lessons";
const changed = () => window.dispatchEvent(new Event(LESSONS_EVENT));

export async function listLessons(): Promise<LessonSummary[]> {
  const { data, error } = await supabase
    .from("lerno_lessons")
    .select("id,title,prompt,created_at")
    .order("created_at", { ascending: false })
    .limit(200);
  if (error) throw error;
  return data ?? [];
}

export async function getLesson(id: string): Promise<Lesson | null> {
  const { data, error } = await supabase.from("lerno_lessons").select("*").eq("id", id).maybeSingle();
  if (error) throw error;
  return data as Lesson | null;
}

export async function createLesson(prompt: string, title: string, scenes: Scene[], lang: string): Promise<string> {
  const { data, error } = await supabase
    .from("lerno_lessons")
    .insert({ prompt, title: title || prompt, scenes, lang })
    .select("id")
    .single();
  if (error) throw error;
  changed();
  return data.id as string;
}

export async function updateLesson(id: string, patch: Partial<Pick<Lesson, "title" | "notes" | "scenes">>) {
  const { error } = await supabase.from("lerno_lessons").update(patch).eq("id", id);
  if (error) throw error;
  if (patch.title) changed();
}

export async function deleteLesson(id: string, userId: string) {
  const { error } = await supabase.from("lerno_lessons").delete().eq("id", id);
  if (error) throw error;
  const { data: files } = await supabase.storage.from("lerno-videos").list(`${userId}/${id}`);
  if (files?.length) await supabase.storage.from("lerno-videos").remove(files.map((f) => `${userId}/${id}/${f.name}`));
  changed();
}

/** Copy the rendered videos from the render server into the user's storage so old lessons keep playing. */
export async function persistVideos(id: string, userId: string, scenes: Scene[]): Promise<Scene[]> {
  const out: Scene[] = [];
  for (const s of scenes) {
    const src = mediaUrl(s.video_url);
    if (!src || src.includes("/storage/v1/object/public/")) { out.push(s); continue; }
    try {
      const blob = await (await fetch(src)).blob();
      const path = `${userId}/${id}/Scene${s.scene_number}.mp4`;
      const { error } = await supabase.storage.from("lerno-videos").upload(path, blob, { contentType: "video/mp4", upsert: true });
      if (error) throw error;
      const { data } = supabase.storage.from("lerno-videos").getPublicUrl(path);
      out.push({ ...s, video_url: data.publicUrl });
    } catch {
      out.push(s);
    }
  }
  await updateLesson(id, { scenes: out });
  return out;
}
