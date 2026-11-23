import { LibraryView } from "@/components/library/library-view";

export default function LibraryPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Library</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          Everything this app wrote under its prefix in B2: each tenant&apos;s adapters and
          manifests, generated images, and run reports. For any other object in the bucket, use Files.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <LibraryView />
      </div>
    </div>
  );
}
