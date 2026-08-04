import type { ReactNode } from "react";

type Props = {
  actions?: ReactNode;
  description: string;
  title: string;
};

export function PageIntro({ actions, description, title }: Props) {
  return (
    <section className="page-intro">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions ? <div className="page-intro-actions">{actions}</div> : null}
    </section>
  );
}
