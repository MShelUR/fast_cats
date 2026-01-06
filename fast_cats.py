import argparse
import getpass
import keyring
import logging
import os
import re
import requests
from sys import exit, path
from tqdm import tqdm
from warnings import warn as warning

import fileutils
from urlogger import URLogger

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

path.append(f'{__location__}/.cats')
from cryptogra_fy import get_credentials


class Fast_cats_session:
    login_url = "https://groups.richmond.edu/login"
    get_groups_url = "https://groups.richmond.edu/groups/mine/?order_by=GROUP_NAME&direction=ASC"
    members_url = "https://groups.richmond.edu/members"
    add_member_url = "https://groups.richmond.edu/members/add"
    del_member_url = "https://groups.richmond.edu/members/delete"
    search_user_url = "https://groups.richmond.edu/members/search/"

    def __init__(self, credentials):
        netid, password = credentials
        self.session = requests.Session()
        self.groups = {}
        self.members = {}
        self.user_affiliations = {}
        # get session from going to page
        logger.debug("obtaining session")
        login_page = self.session.get(self.login_url)
        # log in
        login_payload = {"netid": netid, "password": password, "submit": "1"}
        login_response = self.session.post(self.login_url, data=login_payload, cookies=login_page.cookies)
        if login_response.status_code != 200:
            logger.error(f"couldn't login as user {netid}")
            raise ValueError(f"Couldn't log into CATS as user {netid}")
            exit(1)
        logger.debug(f"logged in as {netid}")
        #  make headers that look like a browser with session and cookies
        self.headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "0",
            "Cookie": "catsgroups="+self.session.cookies.get_dict()['catsgroups'],
            "Host": "groups.richmond.edu",
            "Origin": "https://groups.richmond.edu",
            "Referer": "https://groups.richmond.edu/dashboard/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows"
        }
        # get groups cache
        self.get_groups()

    def __del__(self) -> int:
        if self.session:
            self.session.close()
        return 0

    def get_groups(self) -> list:
        # get (group id, group name) list
        logger.debug("found groups:")
        groups_response = self.session.post(self.get_groups_url, headers=self.headers)
        groups = re.findall(r"<tr id=\"(\d+)\".+\n.+\"group-name\">(.+)<", groups_response.text)
        for group in groups:
            gid, gname = group
            self.groups[gid] = gname
            logger.debug(f"\t{gname}: {gid}")
        return self.groups

    def get_group_gid(self,group_name: str) -> str:
        logger.debug(f"trying to find gid for group {group_name}")
        for gid in self.groups:
            if self.groups[gid].lower() == group_name.lower():
                logger.debug(f"\tgroup {group_name} has gid {gid}")
                return gid
        raise Exception(f"User does not have access to a group named '{group_name}'")

    def get_users_in_group(self, gid: str) -> list:
        # get every user (first, last, department, type, netid) in group, build cache
        logger.debug(f"getting users in group {gid}...")
        members_result = self.session.post(self.members_url+"/"+gid, headers=self.headers)
        members = [re.findall(r"td>(.*)<",member) for member in re.findall(r"<tr id=\".+\">\n(.+\n.+\n.+\n.+\n.+)\n.+<td class=", members_result.text)]
        for u_first, u_last, u_affiliation, u_status, u_netid in members:
            # status is student, faculty, alumni, etc.
            # affiliation is for things like student employees and department; this is potentially blank.
            self.user_affiliations[u_netid] = (u_status,u_affiliation)
        # build local cache to verify existence before adding/removing users later
        self.members[gid] = [member[4] for member in members] # member[4] is netid
        logger.debug(f"found {len(members)} users in group {gid}")
        return members

    def add_user_to_group(self, gid: str, user_netid: str) -> int:
        # add user to group

        logger.debug(f"adding user {user_netid} to group {gid}...")
        # check if user already in group
        if self.is_in_group(gid,user_netid):
            logger.debug(f"\t user {user_netid} was already in group, skipping")
            return 0 # user is in group

        # try to add user
        add_member_result = self.session.post(self.add_member_url+"/"+gid+"/"+user_netid, headers=self.headers)
        if add_member_result.status_code != 200:
            logger.error(f"Could not add {user_netid} to group {gid}")
            raise Exception(f"Could not add {user_netid} to group {gid}")
            exit(1)
        logger.debug(f"\tuser {user_netid} added to group {gid}")
        return 0

    def get_netid_from_user_name(self, user_last, user_first):
        # search for user netid from last and first name
            # if multiple people with same name, raise error

        user_search_payload = {"lname": user_last}

        people_list_response = self.session.post(self.search_user_url,data=user_search_payload, headers=self.headers)
        if people_list_response.status_code != 200:
            logger.error(f"Could not search for user: '{user_last}, {user_first}'")
            raise Exception(f"Could not search for user: '{user_last}, {user_first}'")
        
        people_list_str = people_list_response.text

        # response comes as ["l1, f1 (net1, dep1)","l2, f2 (net2, dep2)"]
        people_list_trimmed = people_list_str[2:-2] # removes leading [" and trailing "]
        people_list = people_list_trimmed.split("\",\"") # splits users

        matched_netid = None
        for person in people_list:
            if person == '':
                continue
            found_last, found_first, netid_and_department = re.findall(r"(.*), (.*) \((.*)\)", person)[0]
            if found_last.lower() == user_last.lower() and found_first.lower() == user_first.lower():
                if matched_netid:
                    logger.error(f"Found multiple people with the name '{user_first}, {user_last}'")
                    raise Exception(f"Found multiple people with the name '{user_first}, {user_last}'")
                matched_netid = netid_and_department.split(", ")[0]

        if not matched_netid:
            logger.warning(f"Could not find user: '{user_last}, {user_first}'")
            print(f"Could not find user: '{user_last}, {user_first}'")

        logger.debug(f"found netid {matched_netid} for user '{user_last}, {user_first}'")

        return matched_netid
        

    def remove_user_from_group(self, gid: str, user_netid: str) -> int:
        # remove user from group

        logger.debug(f"removing user {user_netid} from group {gid}...")
        # check if user already removed from group
        if not self.is_in_group(gid,user_netid):
            logger.debug(f"\t user {user_netid} not in group, skipping")
            return 0 # user isn't in group
        
        # try removing user from group
        del_member_result = self.session.post(self.del_member_url+"/"+gid+"/"+user_netid, headers=self.headers)
        if del_member_result.status_code != 200:
            logger.error(f"Could not delete {user_netid} from group {gid}")
            raise Exception(f"Could not delete {user_netid} from group {gid}")
            exit(1)
        logger.debug(f"user {user_netid} removed from group {gid}")
        return 0

    def is_in_group(self, gid: str, user_netid: str) -> bool:
        # check if user is in group

        logger.debug(f"\tchecking if user {user_netid} is in group {gid}...")
        # check if group exists in cache, else update cache
        if not self.members.get(gid):
            self.get_users_in_group(gid)
        # check if user in group
        if user_netid in self.members[gid]:
            logger.debug(f"\tUser is in group")
            return True
        logger.debug(f"\tUser is not in group")
        return False
        
def parse_netid_input(session, netid_input):
    users = []

    try: # input file
        with open(netid_input,"r") as user_file:
            for line in user_file.read().split("\n"):
                if len(line) == 0:
                    continue # blank line
                if "," in line: # name, fetch netid
                    last, first = re.sub(r"\s+","", line).split(",")
                    found_netid = session.get_netid_from_user_name(last,first)
                    if found_netid:
                        users.append(found_netid)
                else: # just a netid
                    users.append(line)
    except: # one input
        if "," in netid_input: # name, fetch netid
            last, first = re.sub(r"\s+","", netid_input).split(",")
            found_netid = session.get_netid_from_user_name(last,first)
            if found_netid:
                users = [found_netid]
        else: # just a netid
            users = [found_netid]

    return users

def main(args):

    group = args.group
    netid_input = args.input
    do_it = args.do_it
    remove = args.remove
    
    s = Fast_cats_session(get_credentials())
    group_gid = s.get_group_gid(group)

    users = parse_netid_input(s,netid_input)

    if remove:
        for netid in tqdm(users, ascii=True, desc="removing users"):
            if do_it: 
                s.remove_user_from_group(group_gid,netid)
            logger.info(f"removed {netid} from group {group} (gid {group_gid})")
    else:
        users = [v for v in users] # convert generator to list
        for netid in tqdm(users, ascii=True, desc="adding users"):
            if do_it: 
                s.add_user_to_group(group_gid,netid)
            logger.info(f"added {netid} to group {group} (gid {group_gid})")

        # check for adding non students to lists
        
        # first get who was ALREADY in the list before additions
        old_affiliations = s.user_affiliations

        # update affiliations list by getting the group again
        logger.debug("checking statuses of added users")
        s.get_users_in_group(group_gid)
        for netid in users:
            try:
                status, affiliation = s.user_affiliations[netid]
            except:
                continue # user has no affiliation, no need to check
            # if they were already present before running this script, don't remove them.
            if old_affiliations.get(netid):
                continue

            # if they were added from this script, check if their status is valid
            if status != "student":
                logger.warning(f"user {netid} has status {status}, removing")
                s.remove_user_from_group(group_gid,netid)
                logger.info(f"\tremoved {netid} from group {group} (gid {group_gid})")
            else:
                logger.debug(f"\tuser {netid} is a student.")
        

if __name__ == "__main__":
    logger = URLogger(level=logging.INFO, logfile= "logs/fast_cats.log", formatter = logging.Formatter('%(message)s'))
    #logger = logging.getLogger(__name__)
    #logging.basicConfig(filename=f'{__location__}/log_fast_cats.log', level=logging.DEBUG, format='%(asctime)s %(message)s')

    parser = argparse.ArgumentParser(prog="fastcats", 
        description="""
    Create, read, and remove 
    accounts on CATS.
    What CATS does, FastCATS does better!
                        -----
             (\___//)  -----    ...
            (= *.* =)    -----  .   .
                        ----      ..
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-g', '--group', type=str, default='HPC',
        help="Name of group to add the users to. Defaults to HPC (for spydur access)")
    parser.add_argument('-i', '--input', type=str, default="",
        help="Input file name with netids, or the one netid to be added.")
    parser.add_argument('-r', '--remove', action='store_true',
        help="Remove the provided netids from the group.")
    parser.add_argument('-z', '--zap', action='store_true',
        help="Zap the previous log file out of existence!")

    parser.add_argument('--do-it', action='store_true', 
        help="""
    Adding this switch will execute the commands
    as the program runs rather than print what
    actions will be taken.
        """)
    
    args = parser.parse_args()

    if args.zap:
        try:
            os.remove(f'{__location__}/log_fast_cats.log')
        except:
            pass

    if not args.group:
        print("At least one group must be named for this program to run.")
        exit(0)
    if not args.input:
        print("At least one netid or file containing netids must be named.")
        exit(0)

    
    main(args)