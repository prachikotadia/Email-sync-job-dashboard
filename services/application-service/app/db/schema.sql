-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Users Table
create table if not exists users (
    id uuid primary key default uuid_generate_v4(),
    email text unique not null,
    created_at timestamp with time zone default now()
);

-- Companies Table
create table if not exists companies (
    id uuid primary key default uuid_generate_v4(),
    name text unique not null,
    created_at timestamp with time zone default now()
);

-- Roles Table
create table if not exists roles (
    id uuid primary key default uuid_generate_v4(),
    company_id uuid references companies(id) on delete cascade not null,
    title text not null,
    created_at timestamp with time zone default now(),
    unique(company_id, title)
);

-- Resumes Table
create table if not exists resumes (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references users(id), -- Optional owner
    file_name text not null,
    storage_url text not null,
    tags text[] default array[]::text[],
    created_at timestamp with time zone default now()
);

-- Applications Table
create table if not exists applications (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references users(id), -- Optional owner
    company_id uuid references companies(id) on delete cascade not null,
    role_id uuid references roles(id) on delete cascade not null,
    status text not null default 'Applied',
    status_confidence float default 0.0,
    applied_count int default 1,
    last_email_date timestamp with time zone,
    ghosted boolean default false,
    resume_id uuid references resumes(id) on delete set null,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique(company_id, role_id)
);

-- Status History Table (Append-only)
create table if not exists status_history (
    id uuid primary key default uuid_generate_v4(),
    application_id uuid references applications(id) on delete cascade not null,
    status text not null,
    previous_status text,
    changed_at timestamp with time zone default now()
);

-- Application Resumes (Many-to-Many if needed, usually direct link is enough but requested)
create table if not exists application_resumes (
    application_id uuid references applications(id) on delete cascade,
    resume_id uuid references resumes(id) on delete cascade,
    primary key (application_id, resume_id)
);

-- Indexes
create index if not exists idx_companies_name on companies(name);
create index if not exists idx_applications_user on applications(user_id);
create index if not exists idx_applications_status on applications(status);
