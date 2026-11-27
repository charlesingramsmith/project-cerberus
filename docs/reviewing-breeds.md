# Reviewing breeds members have added

Every breed in `data/breeds.csv` is **verified**: it's on the life list and counts towards lifers and badges. When a member can't find a breed on the **Spotted!** tab, they can type it in. The sighting is logged with an **Unverified breed** badge, and the breed's name is added to the `user_breeds` table so other members can pick it too.

## See the list

Quickest: Supabase dashboard > **Table Editor** > `user_breeds`.

To see how popular each one is, open **SQL Editor** > New query, paste this and click **Run** (it only reads data):

```sql
select b.name,
       b.created_at::date as added_on,
       count(s.id) as sightings,
       count(distinct s.user_id) as spotters
from public.user_breeds b
left join public.sightings s on lower(s.breed) = lower(b.name)
where not b.rejected
group by b.id
order by spotters desc, sightings desc, b.name;
```

## Verify a breed

Add it as a row in `data/breeds.csv` with a blank rank (only the AKC top 100 have one; the rest are listed A to Z), plus `data/breed_info.csv`, `data/breed_photos.csv` (rerun `scripts/fetch_breed_photos.py`) and `data/breed_faces.csv` (`scripts/face_cropper.py`). Then move the last badge in `cerberus/logic.py` (`BADGES`, the one for spotting every breed) up to the new number of breeds. The tests check these files match, and that the last badge matches. Use the same spelling as in `user_breeds`, so members' earlier sightings of it count straight away. Its row in `user_breeds` can then be deleted (or left: the app ignores added breeds that are now verified).

## Hide a breed

If a name is a joke, a typo or a duplicate, tick **rejected** on its row. It disappears from everyone's breed picker. Sightings already logged with it keep their name and badge.
