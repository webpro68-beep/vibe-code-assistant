## Migration governance checklist

If this PR changes anything under `backend/alembic/**`, `backend/app/models/**`, or Alembic boot/runtime paths:

- [ ] I ran `python scripts/check_single_alembic_head.py`
- [ ] I confirmed the repo resolves to exactly one Alembic head
- [ ] I validated PostgreSQL full-cycle:
  - [ ] `alembic upgrade head`
  - [ ] `alembic downgrade base`
  - [ ] `alembic upgrade head`
- [ ] I did not rewrite shared migration history
- [ ] If dual-head existed, I added an explicit merge revision
- [ ] I described the migration risk and intent in this PR
