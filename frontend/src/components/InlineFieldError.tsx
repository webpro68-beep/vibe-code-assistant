"use client";

export default function InlineFieldError({
  messages,
}: {
  messages: string[];
}) {
  if (!messages.length) return null;

  return (
    <div className="mt-2 space-y-1">
      {messages.map((message, index) => (
        <p key={`${message}-${index}`} className="text-xs text-rose-300">
          {message}
        </p>
      ))}
    </div>
  );
}
