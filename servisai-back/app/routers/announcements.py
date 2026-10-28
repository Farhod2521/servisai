"""Yangiliklar (e’lonlar): saytga kirganda chiqadigan oyna. Bir vaqtda faqat bittasi faol."""

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select, update

from ..deps import AdminUser, SessionDep
from ..logos import MAX_LOGO_SIZE, LogoError, delete_image, save_image
from ..models import Announcement
from ..schemas import AnnouncementIn, AnnouncementOut

router = APIRouter(prefix="/announcements", tags=["announcements"])
admin_router = APIRouter(prefix="/admin/announcements", tags=["admin"])


@router.get("/active", response_model=AnnouncementOut | None)
async def active(session: SessionDep):
    return await session.scalar(select(Announcement).where(Announcement.is_active).order_by(Announcement.updated_at.desc()).limit(1))


async def _get(session: SessionDep, announcement_id: int) -> Announcement:
    item = await session.get(Announcement, announcement_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "E’lon topilmadi")
    return item


async def _only_this_active(session: SessionDep, item: Announcement) -> None:
    """Bir vaqtda bitta e’lon faol: bittasi yoqilsa, qolganlari o‘chadi."""
    if item.is_active:
        await session.execute(update(Announcement).where(Announcement.id != item.id).values(is_active=False))


@admin_router.get("", response_model=list[AnnouncementOut])
async def admin_list(_: AdminUser, session: SessionDep):
    return (await session.scalars(select(Announcement).order_by(Announcement.is_active.desc(), Announcement.updated_at.desc()))).all()


@admin_router.post("", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED)
async def admin_create(data: AnnouncementIn, _: AdminUser, session: SessionDep):
    item = Announcement(**data.model_dump())
    session.add(item)
    await session.flush()
    await _only_this_active(session, item)
    await session.commit()
    await session.refresh(item)
    return item


@admin_router.patch("/{announcement_id}", response_model=AnnouncementOut)
async def admin_update(announcement_id: int, data: AnnouncementIn, _: AdminUser, session: SessionDep):
    item = await _get(session, announcement_id)
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    await _only_this_active(session, item)
    await session.commit()
    await session.refresh(item)
    return item


@admin_router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete(announcement_id: int, _: AdminUser, session: SessionDep):
    item = await _get(session, announcement_id)
    image = item.image_url
    await session.delete(item)
    await session.commit()
    delete_image(image, "banners")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post("/{announcement_id}/image", response_model=AnnouncementOut)
async def admin_upload_image(announcement_id: int, _: AdminUser, session: SessionDep, file: UploadFile = File(...)):
    item = await _get(session, announcement_id)
    try:
        url = save_image(await file.read(MAX_LOGO_SIZE + 1), "banners")
    except LogoError as e:
        raise HTTPException(e.status, e.message)
    old, item.image_url = item.image_url, url
    await session.commit()
    delete_image(old, "banners")
    await session.refresh(item)
    return item


@admin_router.delete("/{announcement_id}/image", response_model=AnnouncementOut)
async def admin_remove_image(announcement_id: int, _: AdminUser, session: SessionDep):
    item = await _get(session, announcement_id)
    old, item.image_url = item.image_url, None
    await session.commit()
    delete_image(old, "banners")
    await session.refresh(item)
    return item
