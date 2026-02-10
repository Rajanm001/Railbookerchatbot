select package."CASESAFEID__c",
package."KaptioTravel__ExternalName__c",
startlocation."Name",
endlocation."Name",
STRING_AGG(DISTINCT city."Name", ' | ' ORDER BY city."Name") AS Cities,
STRING_AGG(DISTINCT state_province."Name", ' | ' ORDER BY state_province."Name") AS States_provinces,
STRING_AGG(DISTINCT country."Name", ' | ' ORDER BY country."Name") AS Countries,
STRING_AGG(DISTINCT region."Name", ' | ' ORDER BY region."Name") AS Region,
Categories."triptype",
Categories."route",
Categories."train",
package."Rank__c" as PackageRank,
pg."Name" as ProfitabilityGroup,
access."Name" as AccessRule,
package."KaptioTravel__Length__c" as Duration,
package."KaptioTravel__DepartureType__c" as DepartureType,
--Fixed and seasonal dates--
case when package."KaptioTravel__DepartureType__c" = 'Fixed' then (STRING_AGG(DISTINCT to_char(fixeddates."KaptioTravel__Date__c", 'YYYY-MM-DD'), ' | ' ORDER BY to_char(fixeddates."KaptioTravel__Date__c", 'YYYY-MM-DD'))) 
     when package."KaptioTravel__DepartureType__c" = 'Seasonal' then seasondates."seasonaldates"
     else '' end as Departuredates,
salestips."KaptioTravel__Value__c" as SalesTips,
content."PackageDescription",
content."PackageHighlights",
content."PackageInclusions",
content."PackageDaybyDay",
--pacakage URLs--
CASE WHEN access."Name" = 'Amtrak' then 'https://amtrakvacations.com/trips/' || lower(regexp_replace(regexp_replace(trim(package."KaptioTravel__ExternalName__c"),'[^A-Za-z0-9 ]', '', 'g'),'\s+', '-', 'g' ))
     WHEN access."Name" in ('Railbookers','Railbookers UK/CA/US/AU/SG','Railbookers UK/CA/US/NZ/SG','Railbookers US/CA/AU/NZ/SG')THEN  'https://railbookers.com/trips/' || lower(regexp_replace(regexp_replace(trim(package."KaptioTravel__ExternalName__c"),'[^A-Za-z0-9 ]', '', 'g'),'\s+', '-', 'g'))
     WHEN access."Name" = 'Railbookers UK' then 'https://railbookers.co.uk/trips/' || lower(regexp_replace(regexp_replace(trim(package."KaptioTravel__ExternalName__c"),'[^A-Za-z0-9 ]', '', 'g'),'\s+', '-', 'g'))
     WHEN access."Name" = 'Railbookers SG' THEN 'https://railbookers.sg/trips/' ||  lower(regexp_replace(regexp_replace(trim(package."KaptioTravel__ExternalName__c"),'[^A-Za-z0-9 ]', '', 'g'),'\s+', '-', 'g'))
     WHEN access."Name" = 'Railbookers AU' then  'https://railbookers.com.au/trips/' || lower(regexp_replace(regexp_replace(trim(package."KaptioTravel__ExternalName__c"),'[^A-Za-z0-9 ]', '', 'g'),'\s+', '-', 'g'))
     WHEN access."Name" = 'Railbookers NZ' then 'https://railbookers.co.nz/trips/' || lower(regexp_replace(regexp_replace(trim(package."KaptioTravel__ExternalName__c"),'[^A-Za-z0-9 ]', '', 'g'),'\s+', '-', 'g'))
END AS package_url
from kaptio."KaptioTravel__Package__c" package
--Included locations--
left join kaptio."KaptioTravel__PackageDay__c" pday on pday."KaptioTravel__Package__c" = package."Id"
left join kaptio."KaptioTravel__PackageDayLocation__c" pdaylocation on pdaylocation."KaptioTravel__PackageDay__c" = pday."Id"
left join kaptio."KaptioTravel__Location__c" city on city."Id" = pdaylocation."KaptioTravel__Location__c" 
left join kaptio."KaptioTravel__Location__c" state_province on state_province."Id" = 
case when city."KaptioTravel__FullLocationName__c" like '%United States%' then city."KaptioTravel__Location__c" 
     when city."KaptioTravel__FullLocationName__c" like '%Canada%' then city."KaptioTravel__Location__c" 
     when city."KaptioTravel__FullLocationName__c" like '%Australia%' then city."KaptioTravel__Location__c" 
     when city."KaptioTravel__FullLocationName__c" like '%United Kingdom%' then city."KaptioTravel__Location__c" 
     else null end
left join kaptio."KaptioTravel__Location__c" country on country."Id" = 
case when city."KaptioTravel__FullLocationName__c" like '%United States%' then state_province."KaptioTravel__Location__c" 
     when city."KaptioTravel__FullLocationName__c" like '%Canada%' then state_province."KaptioTravel__Location__c" 
     when city."KaptioTravel__FullLocationName__c" like '%Australia%' then state_province."KaptioTravel__Location__c" 
     when city."KaptioTravel__FullLocationName__c" like '%United Kingdom%' then state_province."KaptioTravel__Location__c" 
     else city."KaptioTravel__Location__c"  end
left join kaptio."KaptioTravel__Location__c" region on region."Id" = country."KaptioTravel__Location__c"
LEFT JOIN kaptio."RecordType" rt ON rt."Id" = package."RecordTypeId"
--Package Category split--
LEFT JOIN (
    SELECT
        p."Id",
        -- Trip Type: TripType_A;TripType_B → 'A | B'
        STRING_AGG(
            DISTINCT regexp_replace(cat, '^TripType_', ''),
            ' | ' ORDER BY regexp_replace(cat, '^TripType_', '')
        ) FILTER (WHERE cat LIKE 'TripType_%') AS triptype,
        -- Route: Route_X;Route_Y → 'X | Y'
        STRING_AGG(
            DISTINCT regexp_replace(cat, '^Route_', ''),
            ' | ' ORDER BY regexp_replace(cat, '^Route_', '')
        ) FILTER (WHERE cat LIKE 'Route_%') AS route,
        -- Train: Train_1;Train_2 → '1 | 2'
        STRING_AGG(
            DISTINCT regexp_replace(cat, '^Train_', ''),
            ' | ' ORDER BY regexp_replace(cat, '^Train_', '')
        ) FILTER (WHERE cat LIKE 'Train_%') AS train
    FROM kaptio."KaptioTravel__Package__c" p
    LEFT JOIN LATERAL
        unnest(string_to_array(p."KaptioTravel__Categories__c", ';')) AS cat(cat)
        ON true
    GROUP BY p."Id"
) AS categories
    ON categories."Id" = package."Id"
--Profitability Group Output--
left join kaptio."KaptioTravel__Group__c" pg on pg."Id" = package."KaptioTravel__ProfitabilityGroup__c"
--Access Rule Output--
left join kaptio."KaptioTravel__AccessRule__c" access on access."Id" = package."KaptioTravel__AccessRule__c"
--Package start and end locations--
left join kaptio."KaptioTravel__Location__c" startlocation on startlocation."Id" = package."KaptioTravel__PackageStartLocation__c"
left join kaptio."KaptioTravel__Location__c" endlocation on endlocation."Id" = package."KaptioTravel__PackageEndLocation__c"
---package fixed dates--
left join 
(select
"KaptioTravel__Package__c",
"Name",
"KaptioTravel__Date__c",
"KaptioTravel__DepartureStatus__c"
from kaptio."KaptioTravel__PackageDeparture__c"
where "IsDeleted" = 'false'
and "KaptioTravel__Active__c" = 'true'
and "KaptioTravel__DepartureStatus__c" not like '%cancelled%'
and "KaptioTravel__Date__c" > CURRENT_DATE) as fixeddates on fixeddates."KaptioTravel__Package__c" = package."Id"
--package sales tips--
left join (select "KaptioTravel__Package__c",
"KaptioTravel__Value__c"
from kaptio."KaptioTravel__PackageInformation__c"
where "KaptioTravel__Key__c"  = 'Sales Tips') salestips on salestips."KaptioTravel__Package__c" = package."Id"
--package content --
left join (SELECT 
  p."CASESAFEID__c",
  -- Overview Description
  MAX(
    CASE 
      WHEN (content."KaptioTravel__Title__c" ILIKE '%Overview%' 
        OR content."KaptioTravel__Sort__c" = '1') 
        AND content."KaptioTravel__Type__c" = 'Summary'
      THEN content."KaptioTravel__Body__c"
    END
  ) AS "PackageDescription",
  -- Trip Highlights
  MAX(
    CASE WHEN content."TripHighlights__c" IS NOT NULL 
      THEN content."TripHighlights__c"
    END
  ) AS "PackageHighlights",
  -- Inclusions
  MAX(
    CASE WHEN content."WhatsIncluded__c" IS NOT NULL 
      THEN content."WhatsIncluded__c"
    END
  ) AS "PackageInclusions",
  -- Day-by-Day Breakdown
  STRING_AGG(
    CASE 
      WHEN content."KaptioTravel__Type__c" = 'DaySummary'
        THEN 'Day ' || content."KaptioTravel__Sort__c" || ' - ' || content."KaptioTravel__Title__c" || ' - ' || content."KaptioTravel__Body__c"
      ELSE NULL
    END,
    ' | '
    ORDER BY content."KaptioTravel__Sort__c"::int
  ) AS "PackageDaybyDay"
FROM kaptio."KaptioTravel__Package__c" p
LEFT JOIN kaptio."KaptioTravel__ContentAssignment__c" assignment 
  ON p."Id" = assignment."KaptioTravel__Package__c"
LEFT JOIN kaptio."KaptioTravel__Content__c" content 
  ON content."Id" = assignment."KaptioTravel__Content__c"
WHERE content."RecordTypeId" = '0127Q000001VdAvQAK'
GROUP BY p."CASESAFEID__c") content on content."CASESAFEID__c" = package."Id"
--season dates--
left join (SELECT
  p."CASESAFEID__c" as Id,
  STRING_AGG(
  DISTINCT
  to_char(dates."KaptioTravel__StartDate__c", 'YYYY-MM-DD')
  || ' - '
  || to_char(dates."KaptioTravel__EndDate__c", 'YYYY-MM-DD')
  || ' - '
  || dates."KaptioTravel__DaysOfWeek__c",
  ' | '
  ORDER BY
  to_char(dates."KaptioTravel__StartDate__c", 'YYYY-MM-DD')
  || ' - '
  || to_char(dates."KaptioTravel__EndDate__c", 'YYYY-MM-DD')
  || ' - '
  || dates."KaptioTravel__DaysOfWeek__c"
) AS SeasonalDates
FROM kaptio."KaptioTravel__TimePeriod__c" dates
  JOIN kaptio."KaptioTravel__PackageSchedule__c" schedule
    ON schedule."Id" = dates."KaptioTravel__PackageSchedule__c"
  JOIN kaptio."KaptioTravel__Package__c" p
    ON p."Id" = schedule."KaptioTravel__Package__c"
  WHERE dates."KaptioTravel__EndDate__c" > CURRENT_DATE
    AND p."CASESAFEID__c" <> ''
    group by p."CASESAFEID__c") seasondates on seasondates."id" = package."Id"
--where filters--
where package."KaptioTravel__IsActive__c" = TRUE
  AND rt."Name" = 'Package'
--Group by--
group by package."CASESAFEID__c",
package."KaptioTravel__ExternalName__c",
startlocation."Name",
endlocation."Name",
Categories."triptype",
Categories."route",
Categories."train",
package."Rank__c",
pg."Name",
access."Name",
package."KaptioTravel__Length__c",
package."KaptioTravel__DepartureType__c",
seasondates."seasonaldates",
salestips."KaptioTravel__Value__c",
content."PackageDescription",
content."PackageHighlights",
content."PackageInclusions",
content."PackageDaybyDay";