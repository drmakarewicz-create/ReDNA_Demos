import * as React from "react";

export function Table({ className = "", ...props }: React.HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="relative w-full overflow-auto">
      <table className={`w-full caption-bottom text-sm ${className}`} {...props} />
    </div>
  );
}

export function TableHeader({ className = "", ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={`border-b ${className}`} {...props} />;
}

export function TableBody({ className = "", ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={`[&_tr:last-child]:border-0 ${className}`} {...props} />;
}

export function TableFooter({ className = "", ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tfoot className={`border-t bg-gray-100/50 font-medium [&>tr]:last:border-b-0 ${className}`} {...props} />;
}

export function TableRow({ className = "", ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={`border-b transition-colors hover:bg-gray-100/50 data-[state=selected]:bg-gray-100 ${className}`} {...props} />;
}

export function TableHead({ className = "", ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={`h-12 px-4 text-left align-middle font-medium text-gray-500 [&:has([role=checkbox])]:pr-0 ${className}`}
      {...props}
    />
  );
}

export function TableCell({ className = "", ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`p-4 align-middle [&:has([role=checkbox])]:pr-0 ${className}`} {...props} />;
}

export function TableCaption({ className = "", ...props }: React.HTMLAttributes<HTMLTableCaptionElement>) {
  return <caption className={`mt-4 text-sm text-gray-500 ${className}`} {...props} />;
}
