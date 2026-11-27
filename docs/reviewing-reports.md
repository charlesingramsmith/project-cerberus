# Reviewing reports

Members can tap **Report** on someone else's post in Social, or on a dog's profile page, and pick a reason: **Inappropriate photo**, **Not a dog**, **Spam** or **Something else**. The post or dog is hidden for that member straight away. Everyone else still sees it until you decide. Members never see who reported what.

Reports land in the `reports` table. The daily 8:30 check lists new ones for you.

## See new reports

Supabase dashboard > **SQL Editor** > New query, paste this and click **Run** (it only reads data):

```sql
select r.id, r.created_at, r.reason,
       coalesce('post ' || r.sighting_id, 'dog ' || r.dog_id) as reported,
       coalesce(s.breed, '@' || d.username) as what,
       coalesce(sp.username, dp.username) as posted_by,
       coalesce(s.photo_path, d.photo_path) as photo,
       s.location, s.notes, d.bio,
       rp.username as reported_by,
       count(*) over (partition by r.sighting_id, r.dog_id) as reports_on_it
from public.reports r
left join public.sightings s on s.id = r.sighting_id
left join public.profiles sp on sp.user_id = s.user_id
left join public.dogs d on d.id = r.dog_id
left join public.profiles dp on dp.user_id = d.owner_id
left join public.profiles rp on rp.user_id = r.user_id
where not r.reviewed
order by r.created_at;
```

To look at a photo, open **Storage** > `sighting-photos` and follow the path in `photo`.

## Decide

- **It's fine:** tick **reviewed** on its rows (Table Editor > `reports`). It stays hidden for the member who reported it.
- **Remove it:** delete the post (Table Editor > `sightings`) or the dog (Table Editor > `dogs`), and its photo in Storage. Its reports and tags are deleted with it.
- **The same member keeps breaking the rules:** see "Be a good member" in `legal/terms.md`; you can delete their account under **Authentication > Users**.
